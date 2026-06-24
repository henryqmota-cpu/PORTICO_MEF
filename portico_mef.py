#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
  Programa para Análise de Pórticos Planos
  Método dos Elementos Finitos (MEF)
===========================================================================
  - Elementos de barra com 3 GDL por nó (u, v, θ)
  - Matriz de rigidez local via integração numérica (Gauss-Legendre)
  - Cargas concentradas e distribuídas uniformemente
  - Condições de contorno por técnica dos zeros e um
===========================================================================
"""

import numpy as np
import json
import sys
import os
from leitura_dados import ler_dados
from esforcos_internos import calcular_todos_diagramas, diagramas_para_json


# =========================================================================
# 2. FUNÇÕES DE FORMA E INTEGRAÇÃO NUMÉRICA
# =========================================================================

def pontos_gauss():
    """Retorna pontos e pesos da quadratura de Gauss-Legendre (2 pontos)."""
    xi = 1.0 / np.sqrt(3.0)
    return [(-xi, 1.0), (xi, 1.0)]


def matriz_B(xi, L):
    """
    Monta a matriz B (2x6) para um ponto de integração xi.
    Linha 0: derivadas das funções de translação axial (dN/dx)
    Linha 1: derivadas segundas das funções de flexão (d²N/dx²)
    """
    J = L / 2.0  # Jacobiano

    # Derivadas axiais: dN/dxi dividido pelo Jacobiano
    dN1_ax = (-1.0 / 2.0) / J    # = -1/L
    dN2_ax = (1.0 / 2.0) / J     # =  1/L

    # Derivadas segundas de flexão: d²N/dxi² dividido por J²
    J2 = J * J
    d2N1_fl = (3.0 * xi / 2.0) / J2
    d2N2_fl = (L / 4.0 * (3.0 * xi - 1.0)) / J2
    d2N3_fl = (-3.0 * xi / 2.0) / J2
    d2N4_fl = (L / 4.0 * (3.0 * xi + 1.0)) / J2

    B = np.zeros((2, 6))
    B[0, 0] = dN1_ax
    B[0, 3] = dN2_ax
    B[1, 1] = d2N1_fl
    B[1, 2] = d2N2_fl
    B[1, 4] = d2N3_fl
    B[1, 5] = d2N4_fl

    return B


def matriz_D(E, A, Iz):
    """Monta a matriz constitutiva D (2x2)."""
    return np.array([
        [E * A, 0.0],
        [0.0,   E * Iz]
    ])


# =========================================================================
# 3. MATRIZ DE RIGIDEZ LOCAL (integração numérica)
# =========================================================================

def rigidez_local(E, A, Iz, L):
    """
    Calcula a matriz de rigidez local (6x6) via integração numérica
    de Gauss-Legendre com 2 pontos.
    """
    K = np.zeros((6, 6))
    J = L / 2.0
    D = matriz_D(E, A, Iz)

    for xi, w in pontos_gauss():
        B = matriz_B(xi, L)
        K += B.T @ D @ B * J * w

    return K


# =========================================================================
# 4. MATRIZ DE ROTAÇÃO
# =========================================================================

def matriz_rotacao(cos_a, sin_a):
    """Monta a matriz de rotação R (6x6) para o elemento."""
    R = np.zeros((6, 6))
    R[0, 0] = cos_a;   R[0, 1] = sin_a
    R[1, 0] = -sin_a;  R[1, 1] = cos_a
    R[2, 2] = 1.0
    R[3, 3] = cos_a;   R[3, 4] = sin_a
    R[4, 3] = -sin_a;  R[4, 4] = cos_a
    R[5, 5] = 1.0
    return R


# =========================================================================
# 5. MONTAGEM DO SISTEMA GLOBAL
# =========================================================================

def vetor_correspondencia(ni, nj):
    """
    Retorna o vetor de correspondência (índices 0-based) para os
    graus de liberdade do elemento com nós ni e nj.
    """
    return [3 * (ni - 1),     3 * (ni - 1) + 1, 3 * (ni - 1) + 2,
            3 * (nj - 1),     3 * (nj - 1) + 1, 3 * (nj - 1) + 2]


def condensar_elemento(Ke_local, f_equiv_local, rotula_i, rotula_j):
    """
    Realiza a condensação estática local dos GDLs de rotação liberados.
    Retorna Ke_local_cond (6x6) e f_equiv_local_cond (6) com zeros nos GDLs liberados.
    """
    c = []
    if rotula_i:
        c.append(2)  # Rotação no nó i (theta_i)
    if rotula_j:
        c.append(5)  # Rotação no nó j (theta_j)

    if not c:
        return Ke_local, f_equiv_local

    # GDLs ativos (permanecem)
    r = [i for i in range(6) if i not in c]

    # Particionar as matrizes
    K_rr = Ke_local[np.ix_(r, r)]
    K_rc = Ke_local[np.ix_(r, c)]
    K_cr = Ke_local[np.ix_(c, r)]
    K_cc = Ke_local[np.ix_(c, c)]

    f_r = f_equiv_local[r]
    f_c = f_equiv_local[c]

    # Resolver K_cc_inv
    try:
        K_cc_inv = np.linalg.inv(K_cc)
    except np.linalg.LinAlgError:
        K_cc_inv = np.zeros_like(K_cc)

    # Condensação da rigidez: K* = K_rr - K_rc @ K_cc_inv @ K_cr
    K_cond = K_rr - K_rc @ K_cc_inv @ K_cr

    # Condensação das forças equivalentes: f* = f_r - K_rc @ K_cc_inv @ f_c
    f_cond = f_r - K_rc @ K_cc_inv @ f_c

    # Remontar na dimensão 6x6 com zeros nas linhas/colunas liberadas
    Ke_mod = np.zeros((6, 6))
    f_mod = np.zeros(6)

    for idx_new_i, idx_old_i in enumerate(r):
        f_mod[idx_old_i] = f_cond[idx_new_i]
        for idx_new_j, idx_old_j in enumerate(r):
            Ke_mod[idx_old_i, idx_old_j] = K_cond[idx_new_i, idx_new_j]

    return Ke_mod, f_mod


def reconstruir_elemento_deslocamentos(Ke_local, f_equiv_local, u_local_nodes, rotula_i, rotula_j):
    """
    Reconstrói os deslocamentos (rotações) locais reais nas extremidades rotuladas.
    """
    c = []
    if rotula_i:
        c.append(2)
    if rotula_j:
        c.append(5)

    if not c:
        return u_local_nodes.copy()

    r = [i for i in range(6) if i not in c]

    K_cr = Ke_local[np.ix_(c, r)]
    K_cc = Ke_local[np.ix_(c, c)]
    f_c = f_equiv_local[c]
    u_r = u_local_nodes[r]

    try:
        K_cc_inv = np.linalg.inv(K_cc)
    except np.linalg.LinAlgError:
        K_cc_inv = np.zeros_like(K_cc)

    # u_c = K_cc_inv @ (f_c - K_cr @ u_r)
    u_c = K_cc_inv @ (f_c - K_cr @ u_r)

    u_reconstructed = u_local_nodes.copy()
    for idx, gdl in enumerate(c):
        u_reconstructed[gdl] = u_c[idx]

    return u_reconstructed


def montar_sistema(dados):
    """
    Monta a matriz de rigidez global e o vetor de forças global.
    Retorna também dados auxiliares de cada elemento para pós-processamento.
    """
    n_nos = dados['n_nos']
    n_gdl = 3 * n_nos

    K_global = np.zeros((n_gdl, n_gdl))
    F_global = np.zeros(n_gdl)

    elem_data = {}

    # 1. Determinar liberações de rotação nas extremidades das barras
    rotulas_dados = dados.get('rotulas', {})
    liberacoes = {}
    for elem_id in dados['elementos']:
        info_r = rotulas_dados.get(elem_id, {})
        liberacoes[elem_id] = {
            'rot_i': info_r.get('rot_i', 0) == 1,
            'rot_j': info_r.get('rot_j', 0) == 1
        }

    # Tratar singularidade nodal automática (M-1)
    dados['gdls_bloqueados_estabilidade'] = []
    for N in range(1, n_nos + 1):
        conec = []
        for elem_id, elem in dados['elementos'].items():
            if elem['ni'] == N:
                conec.append((elem_id, 'rot_i'))
            if elem['nj'] == N:
                conec.append((elem_id, 'rot_j'))
        
        if not conec:
            continue
            
        restringido = (N in dados['apoios'] and dados['apoios'][N]['Rz'] == 1) or \
                      (N in dados['apoios_elasticos'] and dados['apoios_elasticos'][N].get('kz', 0.0) > 0)
                      
        if not restringido:
            todas_rotuladas = all(liberacoes[elem_id][tipo] for elem_id, tipo in conec)
            if todas_rotuladas:
                dados['gdls_bloqueados_estabilidade'].append(3 * (N - 1) + 2)
                print(f"    Nota: Nó {N} tem todas as extremidades rotuladas. "
                      f"Para estabilidade matemática, a rotação global deste nó foi bloqueada (o momento resultante continuará nulo).")

    # --- Loop de elementos: montar rigidez global ---
    for elem_id, elem in dados['elementos'].items():
        ni = elem['ni']
        nj = elem['nj']
        mat = dados['materiais'][elem['mat']]
        sec = dados['secoes'][elem['sec']]

        E = mat['E']
        A = sec['A']
        Iz = sec['Iz']

        xi, yi = dados['coords'][ni]
        xj, yj = dados['coords'][nj]
        L = np.sqrt((xj - xi) ** 2 + (yj - yi) ** 2)
        cos_a = (xj - xi) / L
        sin_a = (yj - yi) / L

        # Matriz de rigidez local uncondensed (integração numérica)
        Ke_local = rigidez_local(E, A, Iz, L)
        Ke_local_uncond = Ke_local.copy()

        # Determinar se tem rótulas
        rot_i = liberacoes[elem_id]['rot_i']
        rot_j = liberacoes[elem_id]['rot_j']

        # Força equivalente local uncondensed (se houver carga distribuída)
        f_equiv_local_uncond = np.zeros(6)
        if elem_id in dados['distribuidos']:
            carga = dados['distribuidos'][elem_id]
            qx = carga['qx']
            qy = carga['qy']
            f_equiv_local_uncond = np.array([
                qx * L / 2.0,
                qy * L / 2.0,
                qy * L ** 2 / 12.0,
                qx * L / 2.0,
                qy * L / 2.0,
               -qy * L ** 2 / 12.0
            ])

        # Realizar a condensação estática local
        Ke_local_cond, f_equiv_local_cond = condensar_elemento(
            Ke_local_uncond, f_equiv_local_uncond, rot_i, rot_j
        )

        # Matriz de rotação
        R = matriz_rotacao(cos_a, sin_a)

        # Rigidez global do elemento: Rᵀ · Ke_local_cond · R
        Ke_global = R.T @ Ke_local_cond @ R

        # Vetor de forças global do elemento: Rᵀ · f_equiv_local_cond
        f_equiv_global = R.T @ f_equiv_local_cond

        # Vetor de correspondência
        vc = vetor_correspondencia(ni, nj)

        # Contribuir na matriz de rigidez global e no vetor de forças global
        for i in range(6):
            F_global[vc[i]] += f_equiv_global[i]
            for j in range(6):
                K_global[vc[i], vc[j]] += Ke_global[i, j]

        # Armazenar dados do elemento para pós-processamento
        elem_data[elem_id] = {
            'Ke_local_uncondensed': Ke_local_uncond,
            'Ke_local': Ke_local_cond,  # rigidez condensada local
            'f_equiv_local_uncondensed': f_equiv_local_uncond,
            'f_equiv_local': f_equiv_local_cond,  # forças condensadas locais
            'R': R,
            'L': L,
            'cos': cos_a,
            'sin': sin_a,
            'vc': vc,
            'ni': ni,
            'nj': nj,
            'rot_i': rot_i,
            'rot_j': rot_j,
            'E': E,
            'A': A,
            'Iz': Iz
        }

    # --- Loop de nós com esforços concentrados ---
    for no, carga in dados['concentrados'].items():
        gdl_x  = 3 * (no - 1)
        gdl_y  = 3 * (no - 1) + 1
        gdl_rz = 3 * (no - 1) + 2
        F_global[gdl_x]  += carga['Fx']
        F_global[gdl_y]  += carga['Fy']
        F_global[gdl_rz] += carga['Mz']

    # --- Apoios elásticos (molas): somar rigidez na diagonal ---
    for no, mola in dados.get('apoios_elasticos', {}).items():
        gdl_x  = 3 * (no - 1)
        gdl_y  = 3 * (no - 1) + 1
        gdl_rz = 3 * (no - 1) + 2
        K_global[gdl_x,  gdl_x]  += mola['kx']
        K_global[gdl_y,  gdl_y]  += mola['ky']
        K_global[gdl_rz, gdl_rz] += mola['kz']

    return K_global, F_global, elem_data


# =========================================================================
# 6. CONDIÇÕES DE CONTORNO
# =========================================================================

def aplicar_apoios(K, F, dados):
    """
    Aplica a técnica dos zeros e um para bloquear os graus de
    liberdade correspondentes aos apoios.
    """
    K_mod = K.copy()
    F_mod = F.copy()

    for no, apoio in dados['apoios'].items():
        gdls = [3 * (no - 1), 3 * (no - 1) + 1, 3 * (no - 1) + 2]
        restricoes = [apoio['Dx'], apoio['Dy'], apoio['Rz']]

        for gdl, restrito in zip(gdls, restricoes):
            if restrito == 1:
                K_mod[gdl, :] = 0.0
                K_mod[:, gdl] = 0.0
                K_mod[gdl, gdl] = 1.0
                F_mod[gdl] = 0.0

    # Bloquear GDLs adicionais de estabilidade para evitar singularidade de nós rotulados
    for gdl in dados.get('gdls_bloqueados_estabilidade', []):
        K_mod[gdl, :] = 0.0
        K_mod[:, gdl] = 0.0
        K_mod[gdl, gdl] = 1.0
        F_mod[gdl] = 0.0

    return K_mod, F_mod


# =========================================================================
# 7. SOLUÇÃO DO SISTEMA LINEAR
# =========================================================================

def resolver_sistema(K, F):
    """Resolve o sistema K·U = F."""
    return np.linalg.solve(K, F)


# =========================================================================
# 8. PÓS-PROCESSAMENTO
# =========================================================================

def calcular_reacoes(K_orig, F_orig, U, dados):
    """
    Calcula as reações de apoio: R = K_orig · U - F_orig
    (nos graus de liberdade restringidos).
    Também calcula as reações dos apoios elásticos: R_mola = k · U.
    """
    R_vetor = K_orig @ U - F_orig
    reacoes = []

    for no in sorted(dados['apoios'].keys()):
        apoio = dados['apoios'][no]
        gdls = [3 * (no - 1), 3 * (no - 1) + 1, 3 * (no - 1) + 2]
        restricoes = [apoio['Dx'], apoio['Dy'], apoio['Rz']]
        direcoes = [1, 2, 3]

        for gdl, restrito, direcao in zip(gdls, restricoes, direcoes):
            if restrito == 1:
                reacoes.append((no, direcao, R_vetor[gdl]))

    return reacoes


def calcular_reacoes_elasticas(U, dados):
    """
    Calcula as reações dos apoios elásticos (molas): R = - k · U_gdl.
    Retorna lista de tuplas (no, direcao, valor, k_valor).
    """
    reacoes_el = []
    for no in sorted(dados.get('apoios_elasticos', {}).keys()):
        mola = dados['apoios_elasticos'][no]
        gdl_x  = 3 * (no - 1)
        gdl_y  = 3 * (no - 1) + 1
        gdl_rz = 3 * (no - 1) + 2
        nomes = ['kx', 'ky', 'kz']
        gdls = [gdl_x, gdl_y, gdl_rz]
        direcoes = [1, 2, 3]

        for nome_k, gdl, direcao in zip(nomes, gdls, direcoes):
            k_val = mola[nome_k]
            if abs(k_val) > 1e-12:
                r_val = -k_val * U[gdl]
                reacoes_el.append((no, direcao, r_val, k_val))

    return reacoes_el


def calcular_esforcos_internos(dados, U, elem_data):
    """
    Calcula os esforços internos (Normal, Cortante, Momento Fletor)
    nas extremidades de cada elemento, reconstruindo os deslocamentos locais reais.
    """
    esforcos = {}

    for elem_id in sorted(dados['elementos'].keys()):
        ed = elem_data[elem_id]
        vc = ed['vc']
        Ke_uncond = ed['Ke_local_uncondensed']
        f_equiv_uncond = ed['f_equiv_local_uncondensed']
        R = ed['R']
        L = ed['L']

        # Deslocamentos globais do elemento
        u_global_elem = U[vc]

        # Converter para local
        u_local_nodes = R @ u_global_elem

        # Reconstruir os deslocamentos locais reais para extremidades rotuladas
        u_local_reconstructed = reconstruir_elemento_deslocamentos(
            Ke_uncond, f_equiv_uncond, u_local_nodes, ed['rot_i'], ed['rot_j']
        )

        # Armazenar o vetor local reconstruído em elem_data para uso no cálculo contínuo (elástica)
        ed['u_local'] = u_local_reconstructed

        # Forças de extremidade no sistema local (usando matriz não condensada e deslocamentos reais)
        p = Ke_uncond @ u_local_reconstructed - f_equiv_uncond

        # Esforços internos (forças de extremidade do elemento)
        # Nó i:
        N_i = -p[0]
        V_i =  p[1]
        M_i = -p[2]

        # Nó j:
        N_j =  p[3]
        V_j = -p[4]
        M_j =  p[5]

        # Eliminar -0.0
        valores = [N_i, V_i, M_i, N_j, V_j, M_j]
        for k in range(len(valores)):
            if abs(valores[k]) < 1e-10:
                valores[k] = 0.0
        N_i, V_i, M_i, N_j, V_j, M_j = valores

        esforcos[elem_id] = {
            'ni': ed['ni'], 'nj': ed['nj'],
            'N_i': N_i, 'V_i': V_i, 'M_i': M_i,
            'N_j': N_j, 'V_j': V_j, 'M_j': M_j
        }

    return esforcos


# =========================================================================
# 9. IMPRESSÃO DE RESULTADOS
# =========================================================================

def imprimir_resultados(dados, U, reacoes, esforcos, reacoes_elasticas=None):
    """Imprime os resultados formatados no console."""
    n_nos = dados['n_nos']

    # --- Deslocamentos nodais ---
    print("\nDeslocamentos nodais:")
    print("_" * 57)
    print(f"{'Nó':>5}{'Desl.x':>16}{'Desl.y':>16}{'Rot.z':>18}")
    print("-" * 57)
    for no in range(1, n_nos + 1):
        ux = U[3 * (no - 1)]
        uy = U[3 * (no - 1) + 1]
        rz = U[3 * (no - 1) + 2]
        print(f"{no:>5}{ux:>16.8f}{uy:>16.8f}{rz:>18.8f}")
    print("-" * 57)

    # --- Reações de apoio ---
    print("\nReações de apoio:")
    print("_" * 33)
    print(f"{'Nó':>5}{'Dir.':>6}{'Esforço':>16}")
    print("-" * 33)
    for no, direcao, valor in reacoes:
        print(f"{no:>5}{direcao:>6}{valor:>16.4f}")
    print("-" * 33)

    # --- Reações de apoios elásticos (molas) ---
    if reacoes_elasticas:
        print("\nReações dos apoios elásticos (molas):")
        print("_" * 50)
        print(f"{'Nó':>5}{'Dir.':>6}{'k':>14}{'Esforço':>16}")
        print("-" * 50)
        for no, direcao, valor, k_val in reacoes_elasticas:
            print(f"{no:>5}{direcao:>6}{k_val:>14.2f}{valor:>16.4f}")
        print("-" * 50)

    # --- Esforços internos ---
    print("\nEsforços internos:")
    print("_" * 62)
    print(f"{'Elem.':>5}{'Nó':>5}{'Normal':>14}{'Cortante':>14}{'M. Fletor':>14}")
    print("-" * 62)
    for elem_id in sorted(esforcos.keys()):
        ef = esforcos[elem_id]
        print(f"{elem_id:>5}{ef['ni']:>5}"
              f"{ef['N_i']:>14.4f}{ef['V_i']:>14.4f}{ef['M_i']:>14.4f}")
        print(f"{'':>5}{ef['nj']:>5}"
              f"{ef['N_j']:>14.4f}{ef['V_j']:>14.4f}{ef['M_j']:>14.4f}")
        print("-" * 62)


# =========================================================================
# 10. EXPORTAÇÃO DE RESULTADOS
# =========================================================================

def salvar_resultados(arquivo_saida, dados, U, reacoes, esforcos, diagramas=None, reacoes_elasticas=None, K_global=None, F_global=None, K_mod=None, F_mod=None, elem_data=None):
    """Salva os resultados em um arquivo JSON para visualização."""
    n_nos = dados['n_nos']

    resultado = {
        'nos': {str(no): list(coord)
                for no, coord in dados['coords'].items()},
        'elementos': {str(eid): {'ni': e['ni'], 'nj': e['nj']}
                      for eid, e in dados['elementos'].items()},
        'rotulas': {str(eid): {'rot_i': int(v['rot_i']), 'rot_j': int(v['rot_j'])}
                    for eid, v in dados.get('rotulas', {}).items()},
        'deslocamentos': {},
        'reacoes': [],
        'reacoes_elasticas': [],
        'esforcos': {},
        'apoios': {str(no): apoio
                   for no, apoio in dados['apoios'].items()},
        'apoios_elasticos': {str(no): {'kx': float(m['kx']),
                                        'ky': float(m['ky']),
                                        'kz': float(m['kz'])}
                             for no, m in dados.get('apoios_elasticos', {}).items()},
        'concentrados': {str(no): {'Fx': float(c['Fx']),
                                    'Fy': float(c['Fy']),
                                    'Mz': float(c['Mz'])}
                         for no, c in dados['concentrados'].items()},
        'distribuidos': {str(eid): {'qx': float(c['qx']),
                                     'qy': float(c['qy'])}
                         for eid, c in dados['distribuidos'].items()}
    }

    for no in range(1, n_nos + 1):
        resultado['deslocamentos'][str(no)] = [
            float(U[3 * (no - 1)]),
            float(U[3 * (no - 1) + 1]),
            float(U[3 * (no - 1) + 2])
        ]

    for no, direcao, valor in reacoes:
        resultado['reacoes'].append({
            'no': no, 'dir': direcao, 'valor': float(valor)
        })

    # Reações elásticas (molas)
    if reacoes_elasticas:
        for no, direcao, valor, k_val in reacoes_elasticas:
            resultado['reacoes_elasticas'].append({
                'no': no, 'dir': direcao, 'valor': float(valor), 'k': float(k_val)
            })

    for elem_id, ef in esforcos.items():
        resultado['esforcos'][str(elem_id)] = {
            k: (float(v) if isinstance(v, (float, np.floating)) else v)
            for k, v in ef.items()
        }

    # Incluir dados dos diagramas de esforços internos
    if diagramas is not None:
        resultado['diagramas'] = diagramas

    # Salvar matrizes do sistema e dos elementos se fornecidas
    if K_global is not None:
        resultado['matrizes_sistema'] = {
            'K_global': K_global.tolist(),
            'F_global': F_global.tolist(),
            'K_mod': K_mod.tolist(),
            'F_mod': F_mod.tolist()
        }

    if elem_data is not None:
        for eid, ed in elem_data.items():
            if str(eid) in resultado['elementos']:
                resultado['elementos'][str(eid)]['matrizes'] = {
                    'Ke_local_uncondensed': ed['Ke_local_uncondensed'].tolist(),
                    'Ke_local': ed['Ke_local'].tolist(),
                    'f_equiv_local_uncondensed': ed['f_equiv_local_uncondensed'].tolist(),
                    'f_equiv_local': ed['f_equiv_local'].tolist(),
                    'R': ed['R'].tolist(),
                    'Ke_global': (ed['R'].T @ ed['Ke_local'] @ ed['R']).tolist(),
                    'u_local': ed['u_local'].tolist() if ed.get('u_local') is not None else None
                }

    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"\nResultados salvos em: {arquivo_saida}")


# =========================================================================
# PROGRAMA PRINCIPAL
# =========================================================================

def main():
    if len(sys.argv) < 2:
        print("Uso: python portico_mef.py <arquivo_de_entrada>")
        print("Exemplo: python portico_mef.py 3-EXEMPLO-TESTE.txt")
        sys.exit(1)

    arquivo_entrada = sys.argv[1]

    print("=" * 62)
    print("  ANÁLISE DE PÓRTICO PLANO - MÉTODO DOS ELEMENTOS FINITOS")
    print("=" * 62)

    # 1. Leitura de dados
    print(f"\n>>> Lendo dados de: {arquivo_entrada}")
    dados = ler_dados(arquivo_entrada)
    print(f"    Nós: {dados['n_nos']}  |  Elementos: {dados['n_elementos']}"
          f"  |  Materiais: {dados['n_materiais']}")

    # 2. Montagem do sistema
    print(">>> Montando sistema de equações...")
    K_global, F_global, elem_data = montar_sistema(dados)

    # Salvar cópias originais para cálculo de reações
    K_orig = K_global.copy()
    F_orig = F_global.copy()

    # 3. Aplicar condições de contorno
    print(">>> Aplicando condições de contorno...")
    K_mod, F_mod = aplicar_apoios(K_global, F_global, dados)

    # 4. Verificar Estabilidade Estrutural
    n_gdl = K_mod.shape[0]
    rank = np.linalg.matrix_rank(K_mod)
    
    # Grau de indeterminação estática G = (3b + r) - (3n + h)
    b = len(dados['elementos'])
    n = dados['n_nos']
    h = sum(1 for ed in elem_data.values() if ed['rot_i']) + sum(1 for ed in elem_data.values() if ed['rot_j'])
    
    r = 0
    for no, apoio in dados['apoios'].items():
        r += apoio['Dx'] + apoio['Dy'] + apoio['Rz']
        
    G = (3 * b + r) - (3 * n + h)
    
    print(f">>> Análise de estabilidade: Grau de indeterminação G = {G}")
    if G < 0:
        print(f"    Classificação teórica: Estrutura Hipostática (instável).")
    elif G == 0:
        print(f"    Classificação teórica: Estrutura Isostática.")
    else:
        print(f"    Classificação teórica: Estrutura Hiperestática (grau {G}).")
        
    if rank < n_gdl:
        print("\n" + "#" * 65)
        print(" ERRO CRÍTICO: ESTRUTURA INSTÁVEL / HIPOESTÁTICA")
        print("#" * 65)
        print(" A matriz de rigidez global estrutural é singular.")
        print(" Isso indica que a estrutura possui um mecanismo físico de rotação ou translação livre.")
        print(f" Graus de liberdade ativos: {n_gdl} | Posto da matriz: {rank}")
        print(" Impossível prosseguir com a análise.")
        print("#" * 65 + "\n")
        sys.exit(1)

    # 4b. Resolver sistema
    print(">>> Resolvendo sistema linear...")
    U = resolver_sistema(K_mod, F_mod)

    # 5. Pós-processamento
    print(">>> Calculando reações e esforços internos...")
    reacoes = calcular_reacoes(K_orig, F_orig, U, dados)
    reacoes_elasticas = calcular_reacoes_elasticas(U, dados)
    esforcos = calcular_esforcos_internos(dados, U, elem_data)

    # 5b. Calcular diagramas de esforços (equações analíticas)
    print(">>> Calculando equações dos diagramas de esforços...")
    diagramas = calcular_todos_diagramas(esforcos, dados['distribuidos'], elem_data, U)
    diagramas_json = diagramas_para_json(diagramas)

    # 6. Imprimir resultados
    imprimir_resultados(dados, U, reacoes, esforcos, reacoes_elasticas)

    # 7. Salvar resultados para visualização
    pasta = os.path.dirname(os.path.abspath(arquivo_entrada))
    arquivo_saida = os.path.join(pasta, "resultados.json")
    salvar_resultados(arquivo_saida, dados, U, reacoes, esforcos, diagramas_json, reacoes_elasticas, K_orig, F_orig, K_mod, F_mod, elem_data)

    # 7b. Gerar o memorial de cálculo em docx de forma automática
    print(">>> Gerando memorial de cálculo estrutural (.docx)...")
    try:
        from gerar_memorial import gerar_memorial_docx
        arquivo_memorial = os.path.join(pasta, "Memorial_Calculo_Resultados.docx")
        gerar_memorial_docx(arquivo_saida, arquivo_memorial)
    except Exception as e:
        print(f"Aviso: Não foi possível gerar o memorial de cálculo (.docx). Erro: {e}")

    print("\n>>> Análise concluída com sucesso!")
    print("    Execute 'python visualizacao.py resultados.json' para ver o gráfico.")


if __name__ == '__main__':
    main()
