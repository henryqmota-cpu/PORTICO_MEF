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

        # Matriz de rigidez local (integração numérica)
        Ke_local = rigidez_local(E, A, Iz, L)

        # Matriz de rotação
        R = matriz_rotacao(cos_a, sin_a)

        # Rigidez global do elemento: Rᵀ · Ke_local · R
        Ke_global = R.T @ Ke_local @ R

        # Vetor de correspondência
        vc = vetor_correspondencia(ni, nj)

        # Contribuir na matriz de rigidez global
        for i in range(6):
            for j in range(6):
                K_global[vc[i], vc[j]] += Ke_global[i, j]

        # Armazenar dados do elemento para pós-processamento
        elem_data[elem_id] = {
            'Ke_local': Ke_local,
            'R': R,
            'L': L,
            'cos': cos_a,
            'sin': sin_a,
            'vc': vc,
            'ni': ni,
            'nj': nj,
            'f_equiv_local': np.zeros(6)  # será preenchido se houver carga
        }

    # --- Loop de elementos com carga distribuída ---
    for elem_id, carga in dados['distribuidos'].items():
        qx = carga['qx']
        qy = carga['qy']
        ed = elem_data[elem_id]
        L = ed['L']
        R = ed['R']
        vc = ed['vc']

        # Vetor de forças equivalentes no sistema local
        f_equiv_local = np.array([
            qx * L / 2.0,
            qy * L / 2.0,
            qy * L ** 2 / 12.0,
            qx * L / 2.0,
            qy * L / 2.0,
           -qy * L ** 2 / 12.0
        ])

        # Converter para o sistema global
        f_equiv_global = R.T @ f_equiv_local

        # Contribuir no vetor de forças global
        for i in range(6):
            F_global[vc[i]] += f_equiv_global[i]

        # Armazenar para pós-processamento
        ed['f_equiv_local'] = f_equiv_local

    # --- Loop de nós com esforços concentrados ---
    for no, carga in dados['concentrados'].items():
        gdl_x  = 3 * (no - 1)
        gdl_y  = 3 * (no - 1) + 1
        gdl_rz = 3 * (no - 1) + 2
        F_global[gdl_x]  += carga['Fx']
        F_global[gdl_y]  += carga['Fy']
        F_global[gdl_rz] += carga['Mz']

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


def calcular_esforcos_internos(dados, U, elem_data):
    """
    Calcula os esforços internos (Normal, Cortante, Momento Fletor)
    nas extremidades de cada elemento.

    Procedimento:
      1. Extrair deslocamentos globais do elemento
      2. Converter para coordenadas locais: u_local = R · u_global
      3. Calcular forças de extremidade: p = Ke_local · u_local - f_equiv
      4. Obter esforços internos nas seções de cada nó
    """
    esforcos = {}

    for elem_id in sorted(dados['elementos'].keys()):
        ed = elem_data[elem_id]
        vc = ed['vc']
        Ke = ed['Ke_local']
        R = ed['R']
        L = ed['L']
        f_equiv = ed['f_equiv_local']

        # Deslocamentos globais do elemento
        u_global_elem = U[vc]

        # Converter para local
        u_local = R @ u_global_elem

        # Forças de extremidade no sistema local
        p = Ke @ u_local - f_equiv

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

def imprimir_resultados(dados, U, reacoes, esforcos):
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

def salvar_resultados(arquivo_saida, dados, U, reacoes, esforcos):
    """Salva os resultados em um arquivo JSON para visualização."""
    n_nos = dados['n_nos']

    resultado = {
        'nos': {str(no): list(coord)
                for no, coord in dados['coords'].items()},
        'elementos': {str(eid): {'ni': e['ni'], 'nj': e['nj']}
                      for eid, e in dados['elementos'].items()},
        'deslocamentos': {},
        'reacoes': [],
        'esforcos': {},
        'apoios': {str(no): apoio
                   for no, apoio in dados['apoios'].items()},
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

    for elem_id, ef in esforcos.items():
        resultado['esforcos'][str(elem_id)] = {
            k: (float(v) if isinstance(v, (float, np.floating)) else v)
            for k, v in ef.items()
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

    # 4. Resolver sistema
    print(">>> Resolvendo sistema linear...")
    U = resolver_sistema(K_mod, F_mod)

    # 5. Pós-processamento
    print(">>> Calculando reações e esforços internos...")
    reacoes = calcular_reacoes(K_orig, F_orig, U, dados)
    esforcos = calcular_esforcos_internos(dados, U, elem_data)

    # 6. Imprimir resultados
    imprimir_resultados(dados, U, reacoes, esforcos)

    # 7. Salvar resultados para visualização
    pasta = os.path.dirname(os.path.abspath(arquivo_entrada))
    arquivo_saida = os.path.join(pasta, "resultados.json")
    salvar_resultados(arquivo_saida, dados, U, reacoes, esforcos)

    print("\n>>> Análise concluída com sucesso!")
    print("    Execute 'python visualizacao.py resultados.json' para ver o gráfico.")


if __name__ == '__main__':
    main()
