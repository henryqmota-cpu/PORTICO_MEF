#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
  Módulo de Leitura de Dados para Análise de Pórticos Planos
===========================================================================
"""

import re


def ler_dados(arquivo):
    """
    Lê o arquivo de entrada padronizado e retorna um dicionário
    com todos os dados da estrutura.
    """
    # Tentar diferentes codificações
    conteudo = None
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(arquivo, 'r', encoding=enc) as f:
                conteudo = f.read()
            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue

    if conteudo is None:
        raise FileNotFoundError(f"Não foi possível abrir o arquivo: {arquivo}")

    # Separar em linhas e identificar separadores
    todas_linhas = conteudo.replace('\r\n', '\n').split('\n')

    secoes = []
    secao_atual = []
    for linha in todas_linhas:
        texto = linha.strip()
        if re.match(r'^-{5,}$', texto):
            if secao_atual:
                secoes.append(secao_atual)
                secao_atual = []
        elif texto:
            secao_atual.append(texto)
    if secao_atual:
        secoes.append(secao_atual)

    dados = {}

    # --- Seção 0: Nós e coordenadas ---
    _parse_nos(secoes[0], dados)

    # --- Seção 1: Materiais ---
    _parse_materiais(secoes[1], dados)

    # --- Seção 2: Seções transversais ---
    _parse_secoes(secoes[2], dados)

    # --- Seção 3: Elementos ---
    _parse_elementos(secoes[3], dados)

    # --- Seção 4: Esforços concentrados ---
    _parse_concentrados(secoes[4], dados)

    # --- Seção 5: Cargas distribuídas ---
    _parse_distribuidos(secoes[5], dados)

    # --- Seção 6: Apoios ---
    _parse_apoios(secoes[6], dados)

    return dados


def _encontrar_inteiro(linhas):
    """Encontra o primeiro inteiro isolado em uma lista de linhas."""
    for linha in linhas:
        try:
            return int(linha.strip())
        except ValueError:
            continue
    return None


def _parse_nos(linhas, dados):
    n_nos = _encontrar_inteiro(linhas)
    dados['n_nos'] = n_nos
    coords = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 3:
            try:
                no = int(partes[0])
                x = float(partes[1])
                y = float(partes[2])
                coords[no] = (x, y)
            except ValueError:
                continue
    dados['coords'] = coords


def _parse_materiais(linhas, dados):
    n_mat = _encontrar_inteiro(linhas)
    dados['n_materiais'] = n_mat
    materiais = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 2:
            try:
                mat_id = int(partes[0])
                E = float(partes[1])
                materiais[mat_id] = {'E': E}
            except ValueError:
                continue
    dados['materiais'] = materiais


def _parse_secoes(linhas, dados):
    n_sec = _encontrar_inteiro(linhas)
    dados['n_secoes'] = n_sec
    secoes = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 3:
            try:
                sec_id = int(partes[0])
                A = float(partes[1])
                Iz = float(partes[2])
                secoes[sec_id] = {'A': A, 'Iz': Iz}
            except ValueError:
                continue
    dados['secoes'] = secoes


def _parse_elementos(linhas, dados):
    n_elem = _encontrar_inteiro(linhas)
    dados['n_elementos'] = n_elem
    elementos = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 5:
            try:
                elem_id = int(partes[0])
                ni = int(partes[1])
                nj = int(partes[2])
                mat = int(partes[3])
                sec = int(partes[4])
                elementos[elem_id] = {
                    'ni': ni, 'nj': nj, 'mat': mat, 'sec': sec
                }
            except ValueError:
                continue
    dados['elementos'] = elementos


def _parse_concentrados(linhas, dados):
    n_conc = _encontrar_inteiro(linhas)
    dados['n_concentrados'] = n_conc
    concentrados = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 4:
            try:
                no = int(partes[0])
                Fx = float(partes[1])
                Fy = float(partes[2])
                Mz = float(partes[3])
                concentrados[no] = {'Fx': Fx, 'Fy': Fy, 'Mz': Mz}
            except ValueError:
                continue
    dados['concentrados'] = concentrados


def _parse_distribuidos(linhas, dados):
    n_dist = _encontrar_inteiro(linhas)
    dados['n_distribuidos'] = n_dist
    distribuidos = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 3:
            try:
                elem = int(partes[0])
                qx = float(partes[1])
                qy = float(partes[2])
                distribuidos[elem] = {'qx': qx, 'qy': qy}
            except ValueError:
                continue
    dados['distribuidos'] = distribuidos


def _parse_apoios(linhas, dados):
    n_apoios = _encontrar_inteiro(linhas)
    dados['n_apoios'] = n_apoios
    apoios = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 4:
            try:
                no = int(partes[0])
                Dx = int(partes[1])
                Dy = int(partes[2])
                Rz = int(partes[3])
                apoios[no] = {'Dx': Dx, 'Dy': Dy, 'Rz': Rz}
            except ValueError:
                continue
    dados['apoios'] = apoios
