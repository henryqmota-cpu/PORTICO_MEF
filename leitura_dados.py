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

    # Inicializar dados com chaves e estruturas padrão para garantir integridade
    dados = {
        'n_nos': 0,
        'coords': {},
        'n_materiais': 0,
        'materiais': {},
        'n_secoes': 0,
        'secoes': {},
        'n_elementos': 0,
        'elementos': {},
        'n_concentrados': 0,
        'concentrados': {},
        'n_distribuidos': 0,
        'distribuidos': {},
        'n_apoios': 0,
        'apoios': {},
        'n_apoios_elasticos': 0,
        'apoios_elasticos': {},
        'rotulas': {}
    }

    # Analisar cada seção com base em palavras-chave no cabeçalho
    for sec in secoes:
        if not sec:
            continue
        # Junta as primeiras linhas para identificar o conteúdo da seção
        cabecalho = "\n".join(sec[:3]).lower()

        if "coordenadas dos" in cabecalho or "nós (n)" in cabecalho or "nos (n)" in cabecalho:
            _parse_nos(sec, dados)
        elif "quantidade de materiais" in cabecalho or "características dos materiais" in cabecalho or "materiais" in cabecalho:
            _parse_materiais(sec, dados)
        elif "seções transversais" in cabecalho or "características das seções" in cabecalho or "secoes" in cabecalho or "seções" in cabecalho:
            _parse_secoes(sec, dados)
        elif "elementos de barras" in cabecalho or "vinculação das barras" in cabecalho or "vincula" in cabecalho:
            _parse_elementos(sec, dados)
        elif "esforços concentrados" in cabecalho or "esforos concentrados" in cabecalho or "concentrados" in cabecalho:
            _parse_concentrados(sec, dados)
        elif "carregamento distribuido" in cabecalho or "carregamentos distribuídos" in cabecalho or "distribuidos" in cabecalho or "distribuído" in cabecalho:
            _parse_distribuidos(sec, dados)
        elif "apoios elásticos" in cabecalho or "apoios elǭsticos" in cabecalho or "molas" in cabecalho:
            _parse_apoios_elasticos(sec, dados)
        elif "apoios" in cabecalho or "apoios rígidos" in cabecalho:
            _parse_apoios(sec, dados)
        elif "rótulas" in cabecalho or "rotulas" in cabecalho or "rótula" in cabecalho or "rotula" in cabecalho:
            _parse_rotulas(sec, dados)

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


def _parse_apoios_elasticos(linhas, dados):
    """Parseia a seção opcional de apoios elásticos (molas)."""
    n_molas = _encontrar_inteiro(linhas)
    dados['n_apoios_elasticos'] = n_molas if n_molas is not None else 0
    apoios_elasticos = {}
    for linha in linhas:
        partes = linha.split()
        if len(partes) == 4:
            try:
                no = int(partes[0])
                kx = float(partes[1])
                ky = float(partes[2])
                kz = float(partes[3])
                apoios_elasticos[no] = {'kx': kx, 'ky': ky, 'kz': kz}
            except ValueError:
                continue
    dados['apoios_elasticos'] = apoios_elasticos


def _parse_rotulas(linhas, dados):
    """Parseia a seção opcional de liberação de rotação (rótulas) nas extremidades das barras."""
    n_rot = _encontrar_inteiro(linhas)
    rotulas = {}
    
    # Encontrar o índice da linha com n_rot para pular o cabeçalho
    primeiro_idx = -1
    for idx, linha in enumerate(linhas):
        try:
            if int(linha.strip()) == n_rot:
                primeiro_idx = idx
                break
        except ValueError:
            continue
            
    if primeiro_idx != -1:
        for linha in linhas[primeiro_idx + 1:]:
            partes = linha.split()
            if len(partes) == 3:
                try:
                    elem_id = int(partes[0])
                    rot_i = int(partes[1])
                    rot_j = int(partes[2])
                    rotulas[elem_id] = {'rot_i': rot_i, 'rot_j': rot_j}
                except ValueError:
                    continue
    dados['rotulas'] = rotulas

