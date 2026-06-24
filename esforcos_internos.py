#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
  Módulo de Esforços Internos — Equações Analíticas por Trecho
===========================================================================
  Calcula as equações contínuas de N(x), V(x) e M(x) ao longo de
  cada elemento do pórtico, considerando:
    - Esforços de extremidade (nó i) calculados pelo MEF
    - Cargas distribuídas uniformes (qx, qy) no sistema local
  
  Convenções (sistema local do elemento):
    x : coordenada ao longo do eixo do elemento, 0 ≤ x ≤ L
    N(x) > 0 : tração
    V(x)     : cortante conforme convenção do MEF
    M(x)     : momento fletor conforme convenção do MEF
===========================================================================
"""

import numpy as np


# =========================================================================
# 1. CÁLCULO DOS COEFICIENTES DAS EQUAÇÕES
# =========================================================================

def calcular_equacoes_elemento(N_i, V_i, M_i, L, qx=0.0, qy=0.0):
    """
    Calcula os coeficientes das equações analíticas de N(x), V(x) e M(x)
    para um elemento com esforços no nó i e cargas distribuídas.

    Equações (sistema local):
        N(x) = N_i + qx · x                       (linear se qx ≠ 0)
        V(x) = V_i + qy · x                       (linear se qy ≠ 0)
        M(x) = M_i + V_i · x + (qy · x²) / 2     (parabólico se qy ≠ 0)

    Parâmetros:
        N_i, V_i, M_i : esforços no nó inicial (sistema local)
        L             : comprimento do elemento
        qx            : carga distribuída axial (sistema local)
        qy            : carga distribuída transversal (sistema local)

    Retorna:
        dict com chaves 'N', 'V', 'M', cada uma contendo:
            'coefs'  : lista de coeficientes [a0, a1, a2, ...]
                       onde f(x) = a0 + a1·x + a2·x² + ...
            'grau'   : grau do polinômio
            'L'      : comprimento do elemento
    """
    # Normal: N(x) = N_i + qx · x
    N_coefs = [N_i, qx]
    N_grau = 0 if abs(qx) < 1e-12 else 1

    # Cortante: V(x) = V_i + qy · x
    V_coefs = [V_i, qy]
    V_grau = 0 if abs(qy) < 1e-12 else 1

    # Momento Fletor: M(x) = M_i + V_i · x + (qy / 2) · x²
    M_coefs = [M_i, V_i, qy / 2.0]
    if abs(qy) < 1e-12:
        M_grau = 0 if abs(V_i) < 1e-12 else 1
    else:
        M_grau = 2

    return {
        'N': {'coefs': N_coefs, 'grau': N_grau, 'L': L},
        'V': {'coefs': V_coefs, 'grau': V_grau, 'L': L},
        'M': {'coefs': M_coefs, 'grau': M_grau, 'L': L},
    }


# =========================================================================
# 2. AVALIAÇÃO DAS EQUAÇÕES
# =========================================================================

def avaliar_equacao(coefs, x):
    """
    Avalia o polinômio definido por coefs no ponto x.
    coefs = [a0, a1, a2, ...] → f(x) = a0 + a1·x + a2·x² + ...
    """
    resultado = 0.0
    for i, c in enumerate(coefs):
        resultado += c * (x ** i)
    return resultado


def gerar_pontos_diagrama(equacao, n_pontos=50):
    """
    Gera arrays de pontos (xs, ys) ao longo do elemento para plotagem.

    Parâmetros:
        equacao  : dict com 'coefs' e 'L'
        n_pontos : número de pontos de discretização

    Retorna:
        xs : array de posições ao longo do elemento [0, L]
        ys : array de valores do esforço correspondente
    """
    L = equacao['L']
    coefs = equacao['coefs']
    xs = np.linspace(0.0, L, n_pontos)
    ys = np.array([avaliar_equacao(coefs, x) for x in xs])
    return xs, ys


# =========================================================================
# 3. FORMATAÇÃO DAS EQUAÇÕES COMO TEXTO
# =========================================================================

def formatar_equacao(equacao, tipo='N'):
    """
    Retorna uma string legível da equação em ordem decrescente de grau.

    Parâmetros:
        equacao : dict com 'coefs', 'grau', 'L'
        tipo    : 'N', 'V' ou 'M'

    Retorna:
        string formatada, ex: "M(x) = -7.50·x² + 15.28·x + 15.07"
    """
    coefs = equacao['coefs']
    grau = equacao['grau']

    partes = []

    # Termo quadrático (a2·x²)
    if grau >= 2 and len(coefs) > 2:
        a2 = coefs[2]
        if abs(a2) > 1e-12:
            if not partes:
                sinal_str = "" if a2 >= 0 else "-"
            else:
                sinal_str = " + " if a2 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a2):.2f}·x²")

    # Termo linear (a1·x)
    if grau >= 1 and len(coefs) > 1:
        a1 = coefs[1]
        if abs(a1) > 1e-12:
            if not partes:
                sinal_str = "" if a1 >= 0 else "-"
            else:
                sinal_str = " + " if a1 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a1):.2f}·x")

    # Termo constante (a0)
    a0 = coefs[0]
    if not partes:
        partes.append(f"{a0:.2f}")
    else:
        if abs(a0) > 1e-12:
            sinal_str = " + " if a0 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a0):.2f}")

    expr = ''.join(partes)
    return f"{tipo}(x) = {expr}"


# =========================================================================
# 4. CÁLCULO DE EXTREMOS (para anotação de valores máx/mín)
# =========================================================================

def calcular_extremos(equacao):
    """
    Calcula os valores nos extremos e o ponto de máximo/mínimo (se parabólico).

    Retorna:
        lista de tuplas (x, valor, tipo) onde tipo = 'inicio', 'fim' ou 'extremo'
    """
    coefs = equacao['coefs']
    L = equacao['L']
    grau = equacao['grau']

    pontos = []

    # Valor no início (x=0)
    v0 = avaliar_equacao(coefs, 0.0)
    pontos.append((0.0, v0, 'inicio'))

    # Valor no fim (x=L)
    vL = avaliar_equacao(coefs, L)
    pontos.append((L, vL, 'fim'))

    # Para equação parabólica, encontrar o vértice
    if grau == 2 and len(coefs) > 2:
        a2 = coefs[2]
        a1 = coefs[1]
        if abs(a2) > 1e-12:
            x_extremo = -a1 / (2.0 * a2)
            if 0.0 < x_extremo < L:
                v_extremo = avaliar_equacao(coefs, x_extremo)
                pontos.append((x_extremo, v_extremo, 'extremo'))

    return pontos


# =========================================================================
# 4b. CÁLCULO E FORMATAÇÃO DA ELÁSTICA (DEFORMADA)
# =========================================================================

def calcular_deformada_elemento(u_local, E, A, Iz, L, N_i, V_i, M_i, qx=0.0, qy=0.0):
    """
    Calcula os coeficientes das equações de EA·u(x), EI·v(x) e EI·θ(x).
    Retorna coefs_u, coefs_v, coefs_theta.
    """
    u_i, v_i, theta_i = u_local[0], u_local[1], u_local[2]
    
    # EA·u(x) = (E * A * u_i) + N_i * x + (qx / 2.0) * x^2
    coefs_u = [E * A * u_i, N_i, qx / 2.0]
    
    # EI·v(x) = (E * Iz * v_i) + (E * Iz * theta_i) * x + (M_i / 2.0) * x^2 + (V_i / 6.0) * x^3 + (qy / 24.0) * x^4
    coefs_v = [E * Iz * v_i, E * Iz * theta_i, M_i / 2.0, V_i / 6.0, qy / 24.0]
    
    # EI·θ(x) = (E * Iz * theta_i) + M_i * x + (V_i / 2.0) * x^2 + (qy / 6.0) * x^3
    coefs_theta = [E * Iz * theta_i, M_i, V_i / 2.0, qy / 6.0]
    
    return coefs_u, coefs_v, coefs_theta


def gerar_pontos_deformada(coefs_u, coefs_v, E, A, Iz, L, n_pontos=50):
    """
    Gera pontos discretizados reais u(x) e v(x) ao longo do elemento.
    """
    xs = np.linspace(0.0, L, n_pontos)
    EA = E * A
    EI = E * Iz
    
    us = []
    vs = []
    for x in xs:
        # Avaliar EA·u(x)
        val_u = 0.0
        for i, c in enumerate(coefs_u):
            val_u += c * (x ** i)
        us.append(val_u / EA)
        
        # Avaliar EI·v(x)
        val_v = 0.0
        for i, c in enumerate(coefs_v):
            val_v += c * (x ** i)
        vs.append(val_v / EI)
        
    return xs.tolist(), us, vs


def formatar_equacao_deformada(coefs, tipo='v'):
    """
    Retorna uma string legível da equação de deformação em ordem decrescente de grau.
    tipo: 'v' para flexão (EI·v(x)), 'theta' para rotação (EI·θ(x)) ou 'u' para axial (EA·u(x)).
    """
    partes = []
    
    # Termo quártico (a4·x^4)
    if len(coefs) > 4:
        a4 = coefs[4]
        if abs(a4) > 1e-10:
            if not partes:
                sinal_str = "" if a4 >= 0 else "-"
            else:
                sinal_str = " + " if a4 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a4):.2f}·x^4")
            
    # Termo cúbico (a3·x^3)
    if len(coefs) > 3:
        a3 = coefs[3]
        if abs(a3) > 1e-10:
            if not partes:
                sinal_str = "" if a3 >= 0 else "-"
            else:
                sinal_str = " + " if a3 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a3):.2f}·x^3")
            
    # Termo quadrático (a2·x^2)
    if len(coefs) > 2:
        a2 = coefs[2]
        if abs(a2) > 1e-10:
            if not partes:
                sinal_str = "" if a2 >= 0 else "-"
            else:
                sinal_str = " + " if a2 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a2):.2f}·x^2")
            
    # Termo linear (a1·x)
    if len(coefs) > 1:
        a1 = coefs[1]
        if abs(a1) > 1e-10:
            if not partes:
                sinal_str = "" if a1 >= 0 else "-"
            else:
                sinal_str = " + " if a1 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a1):.2f}·x")
            
    # Termo constante (a0)
    a0 = coefs[0]
    if not partes:
        partes.append(f"{a0:.2f}")
    else:
        if abs(a0) > 1e-10:
            sinal_str = " + " if a0 >= 0 else " - "
            partes.append(f"{sinal_str}{abs(a0):.2f}")
            
    expr = ''.join(partes)
    if tipo == 'v':
        prefixo = "EI·v(x)"
    elif tipo == 'theta':
        prefixo = "EI·θ(x)"
    else:
        prefixo = "EA·u(x)"
    return f"{prefixo} = {expr}"


# =========================================================================
# 5. CÁLCULO DE TODOS OS DIAGRAMAS
# =========================================================================

def calcular_todos_diagramas(esforcos, dados_distribuidos, elementos_info, U=None):
    """
    Calcula as equações e pontos de diagrama para todos os elementos, incluindo as deformadas se U for fornecido.
    """
    diagramas = {}

    for elem_id in sorted(esforcos.keys()):
        ef = esforcos[elem_id]
        info = elementos_info[elem_id]
        L = info['L']
        cos_a = info['cos']
        sin_a = info['sin']
        
        E = info.get('E', 1.0)
        A = info.get('A', 1.0)
        Iz = info.get('Iz', 1.0)
        vc = info.get('vc', [])

        # Obter cargas distribuídas no sistema local (se existirem)
        qx = 0.0
        qy = 0.0
        if elem_id in dados_distribuidos:
            qx = dados_distribuidos[elem_id].get('qx', 0.0)
            qy = dados_distribuidos[elem_id].get('qy', 0.0)

        # Calcular equações
        eqs = calcular_equacoes_elemento(
            N_i=ef['N_i'], V_i=ef['V_i'], M_i=ef['M_i'],
            L=L, qx=qx, qy=qy
        )

        # Gerar pontos para plotagem
        pontos = {}
        extremos = {}
        eq_textos = {}

        for tipo in ['N', 'V', 'M']:
            xs, ys = gerar_pontos_diagrama(eqs[tipo], n_pontos=50)
            pontos[tipo] = {'xs': xs.tolist(), 'ys': ys.tolist()}
            extremos[tipo] = calcular_extremos(eqs[tipo])
            eq_textos[tipo] = formatar_equacao(eqs[tipo], tipo)

        # Deformada
        deformada_info = {}
        if U is not None and len(vc) == 6:
            u_local = info.get('u_local')
            if u_local is None:
                u_global_elem = U[vc]
                R = info['R']
                u_local = R @ u_global_elem
            
            coefs_u, coefs_v, coefs_theta = calcular_deformada_elemento(
                u_local, E, A, Iz, L, ef['N_i'], ef['V_i'], ef['M_i'], qx, qy
            )
            xs_def, us_def, vs_def = gerar_pontos_deformada(
                coefs_u, coefs_v, E, A, Iz, L, n_pontos=50
            )
            
            deformada_info = {
                'coefs_u': coefs_u,
                'coefs_v': coefs_v,
                'coefs_theta': coefs_theta,
                'xs': xs_def,
                'us': us_def,
                'vs': vs_def,
                'eq_u': formatar_equacao_deformada(coefs_u, 'u'),
                'eq_v': formatar_equacao_deformada(coefs_v, 'v'),
                'eq_theta': formatar_equacao_deformada(coefs_theta, 'theta'),
                'E': E,
                'A': A,
                'Iz': Iz
            }

        diagramas[elem_id] = {
            'L': L,
            'cos': cos_a,
            'sin': sin_a,
            'ni': ef['ni'],
            'nj': ef['nj'],
            'equacoes': eqs,
            'pontos': pontos,
            'extremos': extremos,
            'equacoes_texto': eq_textos,
            'deformada': deformada_info
        }

    return diagramas


# =========================================================================
# 6. EXPORTAÇÃO PARA JSON
# =========================================================================

def diagramas_para_json(diagramas):
    """
    Converte os dados dos diagramas para formato serializável em JSON.
    """
    resultado = {}

    for elem_id, diag in diagramas.items():
        elem_json = {
            'L': diag['L'],
            'cos': diag['cos'],
            'sin': diag['sin'],
            'ni': diag['ni'],
            'nj': diag['nj'],
            'pontos': diag['pontos'],
            'extremos': {},
            'equacoes_texto': diag['equacoes_texto'],
            'coeficientes': {},
        }

        for tipo in ['N', 'V', 'M']:
            # Extremos como listas simples
            elem_json['extremos'][tipo] = [
                [float(x), float(val), t]
                for x, val, t in diag['extremos'][tipo]
            ]
            # Coeficientes
            elem_json['coeficientes'][tipo] = [
                float(c) for c in diag['equacoes'][tipo]['coefs']
            ]

        # Adicionar deformada ao JSON se existir
        if 'deformada' in diag and diag['deformada']:
            def_info = diag['deformada']
            elem_json['deformada'] = {
                'coefs_u': [float(c) for c in def_info['coefs_u']],
                'coefs_v': [float(c) for c in def_info['coefs_v']],
                'coefs_theta': [float(c) for c in def_info['coefs_theta']],
                'xs': def_info['xs'],
                'us': def_info['us'],
                'vs': def_info['vs'],
                'eq_u': def_info['eq_u'],
                'eq_v': def_info['eq_v'],
                'eq_theta': def_info['eq_theta'],
                'E': float(def_info['E']),
                'A': float(def_info['A']),
                'Iz': float(def_info['Iz']),
            }

        resultado[str(elem_id)] = elem_json

    return resultado
