#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
  Módulo de Visualização Gráfica - Pórtico Plano (MEF)
===========================================================================
  Lê os resultados do arquivo JSON gerado pelo programa principal
  (portico_mef.py) e exibe graficamente:
    - Geometria original do pórtico
    - Geometria deformada (escala amplificada)
    - Numeração dos nós e elementos
    - Símbolos dos apoios
    - Cargas concentradas e distribuídas (no sistema global)
    - Reações de apoio
    - Diagramas de esforços internos (Normal, Cortante, Fletor)
    - Equações analíticas de cada trecho
===========================================================================
"""

import json
import sys
import os
import numpy as np

import matplotlib
# Usar backend WXAgg para integração com wxPython
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
import matplotlib.patches as patches
from matplotlib.lines import Line2D

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar


# =========================================================================
# 1. LEITURA DOS RESULTADOS
# =========================================================================

def carregar_resultados(arquivo):
    """Carrega os resultados do arquivo JSON."""
    with open(arquivo, 'r', encoding='utf-8') as f:
        resultados = json.load(f)
    return resultados


# =========================================================================
# 2. CÁLCULO DO FATOR DE ESCALA
# =========================================================================

def calcular_fator_escala(resultados, percentual=0.10):
    """
    Calcula o fator de escala para a deformada com base na
    dimensão do pórtico e no deslocamento máximo.
    percentual: fração da dimensão do pórtico para o desl. máximo.
    """
    nos = resultados['nos']
    deslocamentos = resultados['deslocamentos']

    # Dimensões do pórtico
    xs = [coord[0] for coord in nos.values()]
    ys = [coord[1] for coord in nos.values()]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dim_max = max(dx, dy)

    if dim_max == 0:
        dim_max = 1.0

    # Deslocamento máximo (translacional)
    desl_max = 0.0
    for desl in deslocamentos.values():
        mag = np.sqrt(desl[0] ** 2 + desl[1] ** 2)
        if mag > desl_max:
            desl_max = mag

    if desl_max < 1e-12:
        return 1.0

    fator = percentual * dim_max / desl_max
    return fator


# =========================================================================
# 3. DESENHO DOS APOIOS
# =========================================================================

def desenhar_apoio(ax, x, y, apoio, tamanho=0.25):
    """Desenha o símbolo do apoio na posição (x, y)."""
    dx_r = apoio.get('Dx', 0)
    dy_r = apoio.get('Dy', 0)
    rz_r = apoio.get('Rz', 0)

    cor_apoio = '#555555'
    t = tamanho

    if dx_r and dy_r and rz_r:
        # Engaste (retângulo preenchido + linhas de hachura)
        largura = t * 0.8
        altura = t * 0.25
        retangulo = patches.Rectangle(
            (x - largura * 0.5, y - altura), largura, altura,
            facecolor=cor_apoio, edgecolor='black',
            linewidth=1.2, zorder=5
        )
        ax.add_patch(retangulo)
        # Hachura abaixo
        for i in range(5):
            xi = x - largura * 0.5 + i * largura / 4
            ax.plot([xi, xi - t * 0.15], [y - altura, y - altura - t * 0.2],
                    color=cor_apoio, linewidth=1, zorder=4)

    elif dx_r and dy_r:
        # Apoio fixo (triângulo)
        tri_x = [x - t * 0.5, x + t * 0.5, x]
        tri_y = [y - t, y - t, y]
        ax.fill(tri_x, tri_y, color=cor_apoio, edgecolor='black',
                linewidth=1.2, zorder=5)
        # Linha base
        ax.plot([x - t * 0.6, x + t * 0.6], [y - t, y - t],
                color='black', linewidth=1.5, zorder=5)
        # Hachura
        for i in range(5):
            xi = x - t * 0.5 + i * t / 4
            ax.plot([xi, xi - t * 0.15], [y - t, y - t * 1.25],
                    color=cor_apoio, linewidth=1, zorder=4)

    elif dx_r or dy_r:
        # Apoio de 1° gênero (rolete / carrinho) - um círculo + triângulo
        tri_x = [x - t * 0.4, x + t * 0.4, x]
        tri_y = [y - t * 0.7, y - t * 0.7, y]
        ax.fill(tri_x, tri_y, color='white', edgecolor='black',
                linewidth=1.2, zorder=5)
        circulo = patches.Circle((x, y - t * 0.85), t * 0.12,
                                 color=cor_apoio, zorder=5)
        ax.add_patch(circulo)
        ax.plot([x - t * 0.5, x + t * 0.5], [y - t, y - t],
                color='black', linewidth=1.5, zorder=5)


def desenhar_apoio_elastico(ax, x, y, kx, ky, kz, tamanho=0.25):
    """Desenha símbolos de mola elástica no nó (x, y)."""
    cor_mola = '#E67E22'   # Laranja
    t = tamanho
    n_zigzag = 5  # número de ciclos do zigue-zague

    def _desenhar_mola_translacional(ax, x0, y0, dx_dir, dy_dir, comprimento, cor):
        """Desenha uma mola em zigue-zague ao longo de uma direção."""
        # Vetor unitário da direção e perpendicular
        mag = np.sqrt(dx_dir**2 + dy_dir**2)
        if mag < 1e-12:
            return []
        ux, uy = dx_dir / mag, dy_dir / mag
        # Perpendicular
        px, py = -uy, ux
        amplitude = comprimento * 0.12
        artistas = []

        # Trecho reto inicial (10% do comprimento)
        seg_ini = comprimento * 0.1
        xi = x0 + ux * seg_ini
        yi = y0 + uy * seg_ini
        l, = ax.plot([x0, xi], [y0, yi], color=cor, linewidth=1.8, zorder=6)
        artistas.append(l)

        # Zigue-zague
        seg_zz = comprimento * 0.7
        pts_x = [xi]
        pts_y = [yi]
        for i in range(1, n_zigzag * 2 + 1):
            frac = i / (n_zigzag * 2)
            cx = xi + ux * seg_zz * frac
            cy = yi + uy * seg_zz * frac
            sinal = 1.0 if i % 2 == 1 else -1.0
            cx += px * amplitude * sinal
            cy += py * amplitude * sinal
            pts_x.append(cx)
            pts_y.append(cy)

        xf = xi + ux * seg_zz
        yf = yi + uy * seg_zz
        pts_x.append(xf)
        pts_y.append(yf)
        l, = ax.plot(pts_x, pts_y, color=cor, linewidth=1.8, zorder=6)
        artistas.append(l)

        # Trecho reto final (20% do comprimento)
        seg_fim = comprimento * 0.2
        xe = xf + ux * seg_fim
        ye = yf + uy * seg_fim
        l, = ax.plot([xf, xe], [yf, ye], color=cor, linewidth=1.8, zorder=6)
        artistas.append(l)

        # Base hachurada (anteparo)
        base_w = comprimento * 0.25
        l, = ax.plot([xe - py * base_w, xe + py * base_w],
                     [ye + px * base_w, ye - px * base_w],
                     color=cor, linewidth=2.0, zorder=6)
        artistas.append(l)
        for j in range(4):
            fj = (j + 1) / 5
            bx = xe - py * base_w + 2 * py * base_w * fj
            by = ye + px * base_w - 2 * px * base_w * fj
            l, = ax.plot([bx, bx + ux * base_w * 0.4],
                         [by, by + uy * base_w * 0.4],
                         color=cor, linewidth=1.0, zorder=5)
            artistas.append(l)

        return artistas

    artistas = []

    # Mola horizontal (kx) - para a esquerda
    if abs(kx) > 1e-12:
        comp = t * 3.0
        arts = _desenhar_mola_translacional(ax, x, y, -1.0, 0.0, comp, cor_mola)
        artistas.extend(arts)
        lbl = ax.text(x - comp * 0.5, y + t * 0.4,
                      f'kx={kx:.0f}', fontsize=6.5, color=cor_mola,
                      ha='center', va='bottom', fontweight='bold',
                      bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                edgecolor='none', alpha=0.85), zorder=11)
        artistas.append(lbl)

    # Mola vertical (ky) - para baixo
    if abs(ky) > 1e-12:
        comp = t * 3.0
        arts = _desenhar_mola_translacional(ax, x, y, 0.0, -1.0, comp, cor_mola)
        artistas.extend(arts)
        lbl = ax.text(x + t * 0.5, y - comp * 0.5,
                      f'ky={ky:.0f}', fontsize=6.5, color=cor_mola,
                      ha='left', va='center', fontweight='bold',
                      bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                edgecolor='none', alpha=0.85), zorder=11)
        artistas.append(lbl)

    # Mola rotacional (kz) - espiral
    if abs(kz) > 1e-12:
        raio = t * 0.6
        # Desenhar uma espiral com 1.5 voltas
        n_pts = 80
        angulos = np.linspace(0, 1.5 * 2 * np.pi, n_pts)
        r_vals = np.linspace(raio * 0.25, raio, n_pts)
        esp_x = [x + r * np.cos(a) for r, a in zip(r_vals, angulos)]
        esp_y = [y + r * np.sin(a) for r, a in zip(r_vals, angulos)]
        l, = ax.plot(esp_x, esp_y, color=cor_mola, linewidth=1.8, zorder=6)
        artistas.append(l)
        lbl = ax.text(x + raio * 1.3, y + raio * 0.5,
                      f'kz={kz:.0f}', fontsize=6.5, color=cor_mola,
                      ha='left', va='bottom', fontweight='bold',
                      bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                edgecolor='none', alpha=0.85), zorder=11)
        artistas.append(lbl)

    return artistas

# =========================================================================
# 4. FUNÇÕES DE DESENHO DAS CARGAS
# =========================================================================

def _calcular_tamanho_seta(resultados):
    """Calcula o tamanho da seta proporcional à dimensão do pórtico."""
    nos = resultados['nos']
    xs = [c[0] for c in nos.values()]
    ys = [c[1] for c in nos.values()]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dim = max(dx, dy, 1.0)
    return dim * 0.12


def desenhar_cargas_concentradas(ax, resultados, tamanho_seta):
    """
    Desenha as cargas concentradas (Fx, Fy, Mz) nos nós.
    Retorna a lista de artistas criados para toggle.
    """
    concentrados = resultados.get('concentrados', {})
    nos = resultados['nos']
    artistas = []

    cor_forca = '#0066cc'
    cor_momento = '#9933cc'

    for no_id, carga in concentrados.items():
        if no_id not in nos:
            continue
        x, y = nos[no_id]
        Fx = carga.get('Fx', 0.0)
        Fy = carga.get('Fy', 0.0)
        Mz = carga.get('Mz', 0.0)

        # --- Força Fx ---
        if abs(Fx) > 1e-10:
            direcao = 1.0 if Fx > 0 else -1.0
            seta = ax.annotate(
                '', xy=(x, y),
                xytext=(x - direcao * tamanho_seta, y),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.15',
                                color=cor_forca, lw=2.0),
                zorder=10
            )
            artistas.append(seta)
            lbl = ax.text(x - direcao * tamanho_seta * 0.5, y + tamanho_seta * 0.2,
                          f'Fx={Fx:.1f}',
                          fontsize=7, color=cor_forca, ha='center', va='bottom',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.85),
                          zorder=11)
            artistas.append(lbl)

        # --- Força Fy ---
        if abs(Fy) > 1e-10:
            direcao = 1.0 if Fy > 0 else -1.0
            seta = ax.annotate(
                '', xy=(x, y),
                xytext=(x, y - direcao * tamanho_seta),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.15',
                                color=cor_forca, lw=2.0),
                zorder=10
            )
            artistas.append(seta)
            lbl = ax.text(x + tamanho_seta * 0.25, y - direcao * tamanho_seta * 0.5,
                          f'Fy={Fy:.1f}',
                          fontsize=7, color=cor_forca, ha='left', va='center',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.85),
                          zorder=11)
            artistas.append(lbl)

        # --- Momento Mz ---
        if abs(Mz) > 1e-10:
            raio = tamanho_seta * 0.4
            if Mz > 0:
                # Anti-horário: arco de 60° a 300°
                angulo_ini, angulo_fim = 60, 300
                sentido_txt = '(anti-hor.)'
                # Ponta da seta na posição final do arco (300°)
                ang_ponta = np.radians(angulo_fim)
                px = x + raio * np.cos(ang_ponta)
                py = y + raio * np.sin(ang_ponta)
                # Direção tangente anti-horária nesse ponto
                dx_t = np.sin(ang_ponta)
                dy_t = -np.cos(ang_ponta)
            else:
                # Horário: arco de 300° a 60° (desenhado invertido)
                angulo_ini, angulo_fim = 60, 300
                sentido_txt = '(horário)'
                # Ponta da seta na posição inicial do arco (60°)
                ang_ponta = np.radians(angulo_ini)
                px = x + raio * np.cos(ang_ponta)
                py = y + raio * np.sin(ang_ponta)
                # Direção tangente horária nesse ponto
                dx_t = -np.sin(ang_ponta)
                dy_t = np.cos(ang_ponta)

            arco = patches.Arc((x, y), raio * 2, raio * 2,
                               angle=0, theta1=angulo_ini, theta2=angulo_fim,
                               color=cor_momento, lw=2.0, zorder=10)
            ax.add_patch(arco)
            artistas.append(arco)

            # Ponta de seta manual
            tam_ponta = raio * 0.35
            seta_ponta = ax.annotate(
                '', xy=(px, py),
                xytext=(px - dx_t * tam_ponta, py - dy_t * tam_ponta),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.18',
                                color=cor_momento, lw=2.0),
                zorder=10
            )
            artistas.append(seta_ponta)

            lbl = ax.text(x, y + raio + tamanho_seta * 0.15,
                          f'Mz={Mz:.1f} {sentido_txt}',
                          fontsize=7, color=cor_momento, ha='center', va='bottom',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.85),
                          zorder=11)
            artistas.append(lbl)

    return artistas


def desenhar_cargas_distribuidas(ax, resultados, tamanho_seta):
    """
    Desenha as cargas distribuídas nos elementos.
    Retorna a lista de artistas criados para toggle.
    """
    distribuidos = resultados.get('distribuidos', {})
    elementos = resultados['elementos']
    nos = resultados['nos']
    artistas = []

    cor_dist = '#cc6600'
    n_setas = 6  # número de setas ao longo do elemento

    for elem_id, carga in distribuidos.items():
        if elem_id not in elementos:
            continue
        elem = elementos[elem_id]
        ni = str(elem['ni'])
        nj = str(elem['nj'])
        if ni not in nos or nj not in nos:
            continue

        x1, y1 = nos[ni]
        x2, y2 = nos[nj]
        qx = carga.get('qx', 0.0)
        qy = carga.get('qy', 0.0)

        # Vetor do elemento
        Lx = x2 - x1
        Ly = y2 - y1
        L = np.sqrt(Lx ** 2 + Ly ** 2)
        if L < 1e-12:
            continue

        # Vetores unitários: tangente e normal (sistema local)
        tx = Lx / L
        ty = Ly / L
        # Normal perpendicular (rotação de +90°)
        nx = -ty
        ny = tx

        # qx atua na direção tangente local, qy na direção normal local
        # Direção global da carga resultante por seta:
        fx_global = qx * tx + qy * nx
        fy_global = qx * ty + qy * ny

        mag = np.sqrt(fx_global ** 2 + fy_global ** 2)
        if mag < 1e-12:
            continue

        # Tamanho das setas proporcional à carga (normalizado)
        seta_len = tamanho_seta * 0.7

        # Desenhar setas ao longo do elemento
        for i in range(n_setas + 1):
            t_param = i / n_setas
            px = x1 + t_param * Lx
            py = y1 + t_param * Ly

            # Ponto de origem da seta (afastado na direção oposta à carga)
            ox = px - (fx_global / mag) * seta_len
            oy = py - (fy_global / mag) * seta_len

            seta = ax.annotate(
                '', xy=(px, py),
                xytext=(ox, oy),
                arrowprops=dict(arrowstyle='->,head_width=0.2,head_length=0.1',
                                color=cor_dist, lw=1.3),
                zorder=10
            )
            artistas.append(seta)

        # Linha conectando as origens das setas
        origens_x = []
        origens_y = []
        for i in range(n_setas + 1):
            t_param = i / n_setas
            px = x1 + t_param * Lx
            py = y1 + t_param * Ly
            ox = px - (fx_global / mag) * seta_len
            oy = py - (fy_global / mag) * seta_len
            origens_x.append(ox)
            origens_y.append(oy)

        linha, = ax.plot(origens_x, origens_y, color=cor_dist,
                         linewidth=1.3, zorder=10)
        artistas.append(linha)

        # Rótulo no centro do elemento
        xm = (x1 + x2) / 2
        ym = (y1 + y2) / 2
        # Deslocar rótulo na direção oposta à carga
        label_parts = []
        if abs(qx) > 1e-10:
            label_parts.append(f'qx={qx:.1f}')
        if abs(qy) > 1e-10:
            label_parts.append(f'qy={qy:.1f}')
        label_texto = ', '.join(label_parts)

        lbl = ax.text(xm - (fx_global / mag) * seta_len * 1.3,
                      ym - (fy_global / mag) * seta_len * 1.3,
                      f'E{elem_id}: {label_texto}',
                      fontsize=7, color=cor_dist, ha='center', va='center',
                      fontweight='bold',
                      bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                edgecolor='none', alpha=0.85),
                      zorder=11)
        artistas.append(lbl)

    return artistas


# =========================================================================
# 5. FUNÇÕES DE DESENHO DAS REAÇÕES DE APOIO
# =========================================================================

def desenhar_reacoes(ax, resultados, tamanho_seta):
    """
    Desenha as reações de apoio nos nós restringidos.
    Retorna a lista de artistas criados para toggle.
    """
    reacoes = resultados.get('reacoes', [])
    nos = resultados['nos']
    artistas = []

    cor_reacao = '#228B22'
    cor_momento_r = '#006400'

    # Agrupar reações por nó
    reacoes_por_no = {}
    for r in reacoes:
        no = str(r['no'])
        if no not in reacoes_por_no:
            reacoes_por_no[no] = {}
        reacoes_por_no[no][r['dir']] = r['valor']

    for no_id, dirs in reacoes_por_no.items():
        if no_id not in nos:
            continue
        x, y = nos[no_id]

        # --- Reação Rx (dir=1) ---
        Rx = dirs.get(1, 0.0)
        if abs(Rx) > 1e-10:
            direcao = 1.0 if Rx > 0 else -1.0
            seta = ax.annotate(
                '', xy=(x, y),
                xytext=(x - direcao * tamanho_seta, y),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.15',
                                color=cor_reacao, lw=2.2),
                zorder=10
            )
            artistas.append(seta)
            lbl = ax.text(x - direcao * tamanho_seta * 0.5,
                          y - tamanho_seta * 0.25,
                          f'Rx={Rx:.2f}',
                          fontsize=7, color=cor_reacao, ha='center', va='top',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.9),
                          zorder=11)
            artistas.append(lbl)

        # --- Reação Ry (dir=2) ---
        Ry = dirs.get(2, 0.0)
        if abs(Ry) > 1e-10:
            direcao = 1.0 if Ry > 0 else -1.0
            seta = ax.annotate(
                '', xy=(x, y),
                xytext=(x, y - direcao * tamanho_seta),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.15',
                                color=cor_reacao, lw=2.2),
                zorder=10
            )
            artistas.append(seta)
            lbl = ax.text(x - tamanho_seta * 0.3,
                          y - direcao * tamanho_seta * 0.5,
                          f'Ry={Ry:.2f}',
                          fontsize=7, color=cor_reacao, ha='right', va='center',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.9),
                          zorder=11)
            artistas.append(lbl)

        # --- Reação Mz (dir=3) ---
        Mz = dirs.get(3, 0.0)
        if abs(Mz) > 1e-10:
            raio = tamanho_seta * 0.4
            if Mz > 0:
                # Anti-horário
                angulo_ini, angulo_fim = 60, 300
                sentido_txt = '(anti-hor.)'
                ang_ponta = np.radians(angulo_fim)
                px = x + raio * np.cos(ang_ponta)
                py = y + raio * np.sin(ang_ponta)
                dx_t = np.sin(ang_ponta)
                dy_t = -np.cos(ang_ponta)
            else:
                # Horário
                angulo_ini, angulo_fim = 60, 300
                sentido_txt = '(horário)'
                ang_ponta = np.radians(angulo_ini)
                px = x + raio * np.cos(ang_ponta)
                py = y + raio * np.sin(ang_ponta)
                dx_t = -np.sin(ang_ponta)
                dy_t = np.cos(ang_ponta)

            arco = patches.Arc((x, y), raio * 2, raio * 2,
                               angle=0, theta1=angulo_ini, theta2=angulo_fim,
                               color=cor_momento_r, lw=2.0, zorder=10)
            ax.add_patch(arco)
            artistas.append(arco)

            # Ponta de seta manual
            tam_ponta = raio * 0.35
            seta_ponta = ax.annotate(
                '', xy=(px, py),
                xytext=(px - dx_t * tam_ponta, py - dy_t * tam_ponta),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.18',
                                color=cor_momento_r, lw=2.0),
                zorder=10
            )
            artistas.append(seta_ponta)

            lbl = ax.text(x, y - raio - tamanho_seta * 0.2,
                          f'Mz={Mz:.2f} {sentido_txt}',
                          fontsize=7, color=cor_momento_r, ha='center', va='top',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.9),
                          zorder=11)
            artistas.append(lbl)

    # --- Desenhar reações elásticas (molas) ---
    reacoes_el = resultados.get('reacoes_elasticas', [])
    reacoes_el_por_no = {}
    for r in reacoes_el:
        no = str(r['no'])
        if no not in reacoes_el_por_no:
            reacoes_el_por_no[no] = {}
        reacoes_el_por_no[no][r['dir']] = r['valor']

    cor_reacao_el = '#D35400'  # Laranja escuro / ferrugem
    cor_momento_el = '#A04000' # Marrom-alaranjado

    for no_id, dirs in reacoes_el_por_no.items():
        if no_id not in nos:
            continue
        x, y = nos[no_id]

        # --- Mola Rx (dir=1) ---
        Rx = dirs.get(1, 0.0)
        if abs(Rx) > 1e-10:
            direcao = 1.0 if Rx > 0 else -1.0
            seta = ax.annotate(
                '', xy=(x, y),
                xytext=(x - direcao * tamanho_seta, y),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.15',
                                color=cor_reacao_el, lw=2.2),
                zorder=10
            )
            artistas.append(seta)
            lbl = ax.text(x - direcao * tamanho_seta * 0.5,
                          y + tamanho_seta * 0.25,
                          f'R_mola_x={Rx:.2f}',
                          fontsize=7, color=cor_reacao_el, ha='center', va='bottom',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.9),
                          zorder=11)
            artistas.append(lbl)

        # --- Mola Ry (dir=2) ---
        Ry = dirs.get(2, 0.0)
        if abs(Ry) > 1e-10:
            direcao = 1.0 if Ry > 0 else -1.0
            seta = ax.annotate(
                '', xy=(x, y),
                xytext=(x, y - direcao * tamanho_seta),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.15',
                                color=cor_reacao_el, lw=2.2),
                zorder=10
            )
            artistas.append(seta)
            lbl = ax.text(x + tamanho_seta * 0.3,
                          y - direcao * tamanho_seta * 0.5,
                          f'R_mola_y={Ry:.2f}',
                          fontsize=7, color=cor_reacao_el, ha='left', va='center',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.9),
                          zorder=11)
            artistas.append(lbl)

        # --- Mola Mz (dir=3) ---
        Mz = dirs.get(3, 0.0)
        if abs(Mz) > 1e-10:
            raio = tamanho_seta * 0.5
            if Mz > 0:
                # Anti-horário
                angulo_ini, angulo_fim = 60, 300
                sentido_txt = '(anti-hor.)'
                ang_ponta = np.radians(angulo_fim)
                px = x + raio * np.cos(ang_ponta)
                py = y + raio * np.sin(ang_ponta)
                dx_t = np.sin(ang_ponta)
                dy_t = -np.cos(ang_ponta)
            else:
                # Horário
                angulo_ini, angulo_fim = 60, 300
                sentido_txt = '(horário)'
                ang_ponta = np.radians(angulo_ini)
                px = x + raio * np.cos(ang_ponta)
                py = y + raio * np.sin(ang_ponta)
                dx_t = -np.sin(ang_ponta)
                dy_t = np.cos(ang_ponta)

            arco = patches.Arc((x, y), raio * 2, raio * 2,
                               angle=0, theta1=angulo_ini, theta2=angulo_fim,
                               color=cor_momento_el, lw=2.0, zorder=10)
            ax.add_patch(arco)
            artistas.append(arco)

            tam_ponta = raio * 0.35
            seta_ponta = ax.annotate(
                '', xy=(px, py),
                xytext=(px - dx_t * tam_ponta, py - dy_t * tam_ponta),
                arrowprops=dict(arrowstyle='->,head_width=0.3,head_length=0.18',
                                color=cor_momento_el, lw=2.0),
                zorder=10
            )
            artistas.append(seta_ponta)

            lbl = ax.text(x, y + raio + tamanho_seta * 0.2,
                          f'M_mola_z={Mz:.2f} {sentido_txt}',
                          fontsize=7, color=cor_momento_el, ha='center', va='bottom',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor='none', alpha=0.9),
                          zorder=11)
            artistas.append(lbl)

    return artistas


# =========================================================================
# 6. FUNÇÕES DE DESENHO DOS DIAGRAMAS DE ESFORÇOS INTERNOS
# =========================================================================

def _calcular_fator_escala_diagrama(resultados, tipo='N'):
    """
    Calcula o fator de escala para o diagrama de esforços, de modo
    que o valor máximo do diagrama ocupe ~15% da dimensão do pórtico.
    """
    nos = resultados['nos']
    diagramas = resultados.get('diagramas', {})

    # Dimensão do pórtico
    xs = [c[0] for c in nos.values()]
    ys = [c[1] for c in nos.values()]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dim_max = max(dx, dy, 1.0)

    # Valor máximo absoluto do esforço
    val_max = 0.0
    for elem_id, diag in diagramas.items():
        pontos = diag.get('pontos', {}).get(tipo, {})
        ys_vals = pontos.get('ys', [])
        for v in ys_vals:
            if abs(v) > val_max:
                val_max = abs(v)

    if val_max < 1e-12:
        return 1.0

    fator = 0.15 * dim_max / val_max
    return fator


def desenhar_diagrama_esforco(ax, resultados, tipo, cor, fator_escala):
    """
    Desenha o diagrama de um esforço (N, V ou M) para todos os elementos.

    O diagrama é plotado perpendicular ao eixo de cada elemento, com
    preenchimento semi-transparente e valores nos extremos.
    Para o diagrama de momento fletor (M), a convenção usual de engenharia
    civil é aplicada (positivo no lado das fibras tracionadas).
    """
    nos = resultados['nos']
    diagramas = resultados.get('diagramas', {})
    artistas = []
    artistas_eq = []

    # Se for momento fletor, invertemos o sinal de plotagem para desenhar na fibra tracionada
    sinal_tipo = -1.0 if tipo == 'M' else 1.0

    for elem_id, diag in diagramas.items():
        ni = str(diag['ni'])
        nj = str(diag['nj'])
        if ni not in nos or nj not in nos:
            continue

        x1, y1 = nos[ni]
        x2, y2 = nos[nj]
        L = diag['L']
        cos_a = diag['cos']
        sin_a = diag['sin']

        # Normal perpendicular ao elemento (rotação de +90°)
        # tangente: (cos_a, sin_a), normal: (-sin_a, cos_a)
        nx = -sin_a
        ny = cos_a

        # Pontos do diagrama
        pontos = diag.get('pontos', {}).get(tipo, {})
        xs_local = pontos.get('xs', [])
        ys_vals = pontos.get('ys', [])

        if not xs_local or not ys_vals:
            continue

        # Converter para coordenadas globais
        # Cada ponto: posição ao longo do elemento + deslocamento perpendicular
        diag_x = []
        diag_y = []
        base_x = []
        base_y = []

        for x_loc, y_val in zip(xs_local, ys_vals):
            # Posição ao longo do eixo do elemento (coordenadas globais)
            bx = x1 + x_loc * cos_a
            by = y1 + x_loc * sin_a

            base_x.append(bx)
            base_y.append(by)

            # Posição do diagrama (deslocado perpendicular)
            y_plot = y_val * sinal_tipo
            dx = bx + y_plot * fator_escala * nx
            dy = by + y_plot * fator_escala * ny
            diag_x.append(dx)
            diag_y.append(dy)

        # Plotar a curva do diagrama
        linha, = ax.plot(diag_x, diag_y, color=cor, linewidth=1.8, zorder=12)
        artistas.append(linha)

        # Preenchimento entre o eixo do elemento e a curva
        # Montar polígono fechado: base_inicio -> diag -> base_fim -> base (volta)
        poly_x = base_x + diag_x[::-1]
        poly_y = base_y + diag_y[::-1]
        fill = ax.fill(poly_x, poly_y, color=cor, alpha=0.15, zorder=11)
        artistas.extend(fill)

        # Linhas de fechamento nos extremos (início e fim)
        l_ini, = ax.plot([base_x[0], diag_x[0]], [base_y[0], diag_y[0]],
                         color=cor, linewidth=1.0, linestyle='-', zorder=12)
        artistas.append(l_ini)

        l_fim, = ax.plot([base_x[-1], diag_x[-1]], [base_y[-1], diag_y[-1]],
                         color=cor, linewidth=1.0, linestyle='-', zorder=12)
        artistas.append(l_fim)

        # Anotações de valores nos extremos e extremos da equação
        extremos = diag.get('extremos', {}).get(tipo, [])
        for ext in extremos:
            x_loc = ext[0]
            val = ext[1]
            tipo_pt = ext[2]

            if abs(val) < 1e-10:
                continue

            # Posição no eixo do elemento
            bx = x1 + x_loc * cos_a
            by = y1 + x_loc * sin_a

            # Posição do valor (no ponto do diagrama)
            val_plot = val * sinal_tipo
            vx = bx + val_plot * fator_escala * nx
            vy = by + val_plot * fator_escala * ny

            # Deslocamento extra do texto para não sobrepor a curva
            offset_x = val_plot * fator_escala * nx * 0.15
            offset_y = val_plot * fator_escala * ny * 0.15

            lbl = ax.text(vx + offset_x, vy + offset_y,
                          f'{val:.2f}',
                          fontsize=7, color=cor, ha='center', va='center',
                          fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                    edgecolor=cor, alpha=0.9, linewidth=0.5),
                          zorder=15)
            artistas.append(lbl)

        # Equação do elemento (texto junto ao meio da barra)
        eq_texto = diag.get('equacoes_texto', {}).get(tipo, '')
        if eq_texto:
            xm = (x1 + x2) / 2
            ym = (y1 + y2) / 2

            # Deslocar na direção perpendicular (oposta ao diagrama, para não sobrepor)
            # Encontrar o sinal médio do diagrama para decidir o lado
            media_vals = np.mean(ys_vals) if ys_vals else 0.0
            sinal = 1.0 if (media_vals * sinal_tipo) >= 0 else -1.0
            offset_eq = 0.12 * max(max([abs(c[0]) for c in nos.values()]) - min([c[0] for c in nos.values()]),
                                    max([abs(c[1]) for c in nos.values()]) - min([c[1] for c in nos.values()]),
                                    1.0)

            eq_x = xm + sinal * offset_eq * nx
            eq_y = ym + sinal * offset_eq * ny

            # Calcular o ângulo do elemento para rotacionar o texto
            angulo_deg = np.degrees(np.arctan2(sin_a, cos_a))
            # Manter o texto legível (não de cabeça para baixo)
            if angulo_deg > 90:
                angulo_deg -= 180
            elif angulo_deg < -90:
                angulo_deg += 180

            eq_lbl = ax.text(eq_x, eq_y,
                             f'E{elem_id}: {eq_texto}',
                             fontsize=6.5, color=cor, ha='center', va='center',
                             fontstyle='italic',
                             rotation=angulo_deg,
                             rotation_mode='anchor',
                             bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                       edgecolor=cor, alpha=0.92, linewidth=0.8),
                             zorder=16)
            artistas_eq.append(eq_lbl)

    return artistas, artistas_eq

# =========================================================================
# 7. PLOT PRINCIPAL
# =========================================================================

# =========================================================================
# 7. FUNÇÃO DE DESENHO MODULAR
# =========================================================================

def desenhar_grafico(ax, resultados, estado, estado_eq, fat_deformada, fat_N, fat_V, fat_M):
    """
    Plota a geometria e diagramas nos eixos fornecidos.
    """
    nos = resultados['nos']
    elementos = resultados['elementos']
    deslocamentos = resultados['deslocamentos']
    apoios = resultados.get('apoios', {})
    diagramas = resultados.get('diagramas', {})

    # ---- Configurar eixos ----
    ax.set_aspect('equal')
    ax.grid(True, linestyle='--', alpha=0.3, color='#cccccc')

    # ---- Plotar elementos (original) ----
    for elem_id, elem in elementos.items():
        ni = str(elem['ni'])
        nj = str(elem['nj'])
        x_orig = [nos[ni][0], nos[nj][0]]
        y_orig = [nos[ni][1], nos[nj][1]]

        ax.plot(x_orig, y_orig, color='#a0a0a0', linewidth=3.0,
                solid_capstyle='round', zorder=2)

        # Rótulo do elemento no ponto médio
        xm = (x_orig[0] + x_orig[1]) / 2
        ym = (y_orig[0] + y_orig[1]) / 2
        dx = x_orig[1] - x_orig[0]
        dy = y_orig[1] - y_orig[0]
        L = np.sqrt(dx ** 2 + dy ** 2)
        if L > 0:
            nx_perp = -dy / L * 0.15
            ny_perp = dx / L * 0.15
        else:
            nx_perp = 0.0
            ny_perp = 0.15

        ax.text(xm + nx_perp, ym + ny_perp, f'E{elem_id}',
                fontsize=8, color='#666666', ha='center', va='center',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                          edgecolor='#cccccc', alpha=0.8),
                zorder=8)

    # ---- Desenhar Rótulas (Articulações) nas extremidades das barras ou nos nós ----
    rotulas_dados = resultados.get('rotulas', {})
    tamanho_seta = _calcular_tamanho_seta(resultados)
    d_offset = 0.12 * tamanho_seta
    r_circ = 0.05 * tamanho_seta
    r_circ_no = 0.07 * tamanho_seta

    no_rotulado_completo = {}
    for no_id in nos:
        conec = []
        for elem_id, elem in elementos.items():
            if str(elem['ni']) == no_id:
                conec.append((elem_id, 'rot_i'))
            if str(elem['nj']) == no_id:
                conec.append((elem_id, 'rot_j'))
        
        if len(conec) > 1:
            todas_rotuladas = True
            for elem_id, tipo in conec:
                rot = rotulas_dados.get(str(elem_id), {})
                if rot.get(tipo, 0) != 1:
                    todas_rotuladas = False
                    break
            if todas_rotuladas:
                no_rotulado_completo[no_id] = True

    # Rótulas nos nós
    for no_id, coord in nos.items():
        if no_rotulado_completo.get(no_id, False):
            circulo = patches.Circle((coord[0], coord[1]), r_circ_no, facecolor='white',
                                     edgecolor='#2c3e50', linewidth=1.8, zorder=10)
            ax.add_patch(circulo)

    # Rótulas de extremidades com offset
    for elem_id, elem in elementos.items():
        ni = str(elem['ni'])
        nj = str(elem['nj'])
        x1, y1 = nos[ni]
        x2, y2 = nos[nj]
        dx = x2 - x1
        dy = y2 - y1
        L = np.sqrt(dx ** 2 + dy ** 2)
        if L < 1e-12:
            continue
            
        rot = rotulas_dados.get(str(elem_id), {})
        rot_i = rot.get('rot_i', 0) == 1
        rot_j = rot.get('rot_j', 0) == 1
        
        if rot_i and not no_rotulado_completo.get(ni, False):
            x_circ = x1 + (dx / L) * d_offset
            y_circ = y1 + (dy / L) * d_offset
            circulo = patches.Circle((x_circ, y_circ), r_circ, facecolor='white',
                                     edgecolor='#2c3e50', linewidth=1.5, zorder=10)
            ax.add_patch(circulo)
            
        if rot_j and not no_rotulado_completo.get(nj, False):
            x_circ = x2 - (dx / L) * d_offset
            y_circ = y2 - (dy / L) * d_offset
            circulo = patches.Circle((x_circ, y_circ), r_circ, facecolor='white',
                                     edgecolor='#2c3e50', linewidth=1.5, zorder=10)
            ax.add_patch(circulo)

    # ---- Plotar elementos (deformada) ----
    if estado['delta']:
        for elem_id, elem in elementos.items():
            ni = str(elem['ni'])
            nj = str(elem['nj'])
            x1, y1 = nos[ni]
            x2, y2 = nos[nj]

            diag = diagramas.get(str(elem_id), {})
            def_info = diag.get('deformada', {})
            
            if def_info:
                xs_loc = def_info.get('xs', [])
                us_vals = def_info.get('us', [])
                vs_vals = def_info.get('vs', [])
                cos_a = diag['cos']
                sin_a = diag['sin']
                
                diag_x = []
                diag_y = []
                for x_loc, u_val, v_val in zip(xs_loc, us_vals, vs_vals):
                    bx = x1 + x_loc * cos_a
                    by = y1 + x_loc * sin_a
                    dx = bx + fat_deformada * (u_val * cos_a - v_val * sin_a)
                    dy = by + fat_deformada * (u_val * sin_a + v_val * cos_a)
                    diag_x.append(dx)
                    diag_y.append(dy)
                    
                ax.plot(diag_x, diag_y, color='#e74c3c',
                        linewidth=1.8, linestyle='--', solid_capstyle='round',
                        zorder=3)

                # Rótulas na deformada
                rot = rotulas_dados.get(str(elem_id), {})
                rot_i = rot.get('rot_i', 0) == 1
                rot_j = rot.get('rot_j', 0) == 1
                if rot_i and not no_rotulado_completo.get(ni, False) and len(diag_x) > 1:
                    lx = diag_x[1] - diag_x[0]
                    ly = diag_y[1] - diag_y[0]
                    l_seg = np.sqrt(lx**2 + ly**2)
                    if l_seg > 1e-12:
                        xd_circ = diag_x[0] + (lx / l_seg) * d_offset
                        yd_circ = diag_y[0] + (ly / l_seg) * d_offset
                        circ_def = patches.Circle((xd_circ, yd_circ), r_circ, facecolor='white',
                                                 edgecolor='#e74c3c', linewidth=1.2, zorder=10)
                        ax.add_patch(circ_def)
                if rot_j and not no_rotulado_completo.get(nj, False) and len(diag_x) > 1:
                    lx = diag_x[-1] - diag_x[-2]
                    ly = diag_y[-1] - diag_y[-2]
                    l_seg = np.sqrt(lx**2 + ly**2)
                    if l_seg > 1e-12:
                        xd_circ = diag_x[-1] - (lx / l_seg) * d_offset
                        yd_circ = diag_y[-1] - (ly / l_seg) * d_offset
                        circ_def = patches.Circle((xd_circ, yd_circ), r_circ, facecolor='white',
                                                 edgecolor='#e74c3c', linewidth=1.2, zorder=10)
                        ax.add_patch(circ_def)
                
                # Equações da deformada
                if estado_eq['delta']:
                    eq_u = def_info.get('eq_u', '')
                    eq_v = def_info.get('eq_v', '')
                    if eq_u or eq_v:
                        eq_texto = ""
                        if eq_v:
                            eq_texto += eq_v
                        if eq_u:
                            if eq_texto:
                                eq_texto += "\n"
                            eq_texto += eq_u
                            
                        xm = (x1 + x2) / 2
                        ym = (y1 + y2) / 2

                        media_vs = np.mean(vs_vals) if vs_vals else 0.0
                        sinal = -1.0 if media_vs >= 0 else 1.0
                        offset_eq = 0.12 * max(max([abs(c[0]) for c in nos.values()]) - min([c[0] for c in nos.values()]),
                                                max([abs(c[1]) for c in nos.values()]) - min([c[1] for c in nos.values()]),
                                                1.0)
                        
                        nx = -sin_a
                        ny = cos_a
                        eq_x = xm + sinal * offset_eq * nx
                        eq_y = ym + sinal * offset_eq * ny

                        angulo_deg = np.degrees(np.arctan2(sin_a, cos_a))
                        if angulo_deg > 90:
                            angulo_deg -= 180
                        elif angulo_deg < -90:
                            angulo_deg += 180

                        ax.text(eq_x, eq_y, f"E{elem_id}:\n{eq_texto}",
                                fontsize=6.0, color='#e74c3c', ha='center', va='center',
                                fontstyle='italic', rotation=angulo_deg, rotation_mode='anchor',
                                bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                                          edgecolor='#e74c3c', alpha=0.92, linewidth=0.8),
                                zorder=16)
            else:
                # Fallback para linha reta se não houver dados de deformada
                xi_d = nos[ni][0] + deslocamentos[ni][0] * fat_deformada
                yi_d = nos[ni][1] + deslocamentos[ni][1] * fat_deformada
                xj_d = nos[nj][0] + deslocamentos[nj][0] * fat_deformada
                yj_d = nos[nj][1] + deslocamentos[nj][1] * fat_deformada

                ax.plot([xi_d, xj_d], [yi_d, yj_d], color='#e74c3c',
                        linewidth=1.8, linestyle='--', solid_capstyle='round',
                        zorder=3)

                rot = rotulas_dados.get(str(elem_id), {})
                rot_i = rot.get('rot_i', 0) == 1
                rot_j = rot.get('rot_j', 0) == 1
                dx_d = xj_d - xi_d
                dy_d = yj_d - yi_d
                L_d = np.sqrt(dx_d**2 + dy_d**2)
                if L_d > 1e-12:
                    if rot_i and not no_rotulado_completo.get(ni, False):
                        xd_circ = xi_d + (dx_d / L_d) * d_offset
                        yd_circ = yi_d + (dy_d / L_d) * d_offset
                        circ_def = patches.Circle((xd_circ, yd_circ), r_circ, facecolor='white',
                                                 edgecolor='#e74c3c', linewidth=1.2, zorder=10)
                        ax.add_patch(circ_def)
                    if rot_j and not no_rotulado_completo.get(nj, False):
                        xd_circ = xj_d - (dx_d / L_d) * d_offset
                        yd_circ = yj_d - (dy_d / L_d) * d_offset
                        circ_def = patches.Circle((xd_circ, yd_circ), r_circ, facecolor='white',
                                                 edgecolor='#e74c3c', linewidth=1.2, zorder=10)
                        ax.add_patch(circ_def)

        # Rótulas completas deformadas
        for no_id in nos:
            if no_rotulado_completo.get(no_id, False):
                coord = nos[no_id]
                desl = deslocamentos[no_id]
                xd = coord[0] + desl[0] * fat_deformada
                yd = coord[1] + desl[1] * fat_deformada
                circ_def = patches.Circle((xd, yd), r_circ_no, facecolor='white',
                                         edgecolor='#e74c3c', linewidth=1.5, zorder=10)
                ax.add_patch(circ_def)

        # Nós deformados
        for no_id in nos:
            coord = nos[no_id]
            desl = deslocamentos[no_id]
            xd = coord[0] + desl[0] * fat_deformada
            yd = coord[1] + desl[1] * fat_deformada
            ax.plot(xd, yd, 's', color='#e74c3c', markersize=6,
                    zorder=7, markeredgecolor='white', markeredgewidth=0.8)

    # ---- Plotar nós (original) ----
    for no_id, coord in nos.items():
        ax.plot(coord[0], coord[1], 'o', color='#2c3e50',
                markersize=8, zorder=6, markeredgecolor='white',
                markeredgewidth=1)
        ax.text(coord[0] + 0.15, coord[1] + 0.2, f'{no_id}',
                fontsize=10, color='#2c3e50', fontweight='bold',
                ha='left', va='bottom', zorder=9)

    # ---- Desenhar apoios rígidos ----
    for no_id, apoio in apoios.items():
        coord = nos[no_id]
        desenhar_apoio(ax, coord[0], coord[1], apoio)

    # ---- Desenhar apoios elásticos ----
    apoios_elasticos = resultados.get('apoios_elasticos', {})
    for no_id, mola in apoios_elasticos.items():
        if no_id in nos:
            coord = nos[no_id]
            desenhar_apoio_elastico(ax, coord[0], coord[1],
                                   mola.get('kx', 0.0),
                                   mola.get('ky', 0.0),
                                   mola.get('kz', 0.0))

    # ---- Desenhar cargas e reações ----
    if estado['F']:
        desenhar_cargas_concentradas(ax, resultados, tamanho_seta)
        desenhar_cargas_distribuidas(ax, resultados, tamanho_seta)

    if estado['R']:
        desenhar_reacoes(ax, resultados, tamanho_seta)

    # ---- Desenhar diagramas ----
    cores_diag = {
        'N': '#1565C0',
        'V': '#E65100',
        'M': '#6A1B9A',
    }

    if estado['N']:
        _, eq_normal = desenhar_diagrama_esforco(ax, resultados, 'N', cores_diag['N'], fat_N)
        if not estado_eq['N']:
            for a in eq_normal:
                a.set_visible(False)

    if estado['V']:
        _, eq_cortante = desenhar_diagrama_esforco(ax, resultados, 'V', cores_diag['V'], fat_V)
        if not estado_eq['V']:
            for a in eq_cortante:
                a.set_visible(False)

    if estado['M']:
        _, eq_fletor = desenhar_diagrama_esforco(ax, resultados, 'M', cores_diag['M'], fat_M)
        if not estado_eq['M']:
            for a in eq_fletor:
                a.set_visible(False)

    # ---- Legenda dinâmica ----
    legenda_handles = [
        Line2D([0], [0], color='#a0a0a0', linewidth=3, label='Geometria original'),
    ]
    if estado['delta']:
        legenda_handles.append(
            Line2D([0], [0], color='#e74c3c', linewidth=1.8, linestyle='--',
                   label=f'Deformada ({fat_deformada:.0f}x)')
        )
    if estado['F']:
        legenda_handles.append(
            Line2D([0], [0], color='#0066cc', linewidth=2, marker='>', markersize=5, label='Forças aplicadas')
        )
    if estado['R']:
        legenda_handles.append(
            Line2D([0], [0], color='#228B22', linewidth=2, marker='>', markersize=5, label='Reações de apoio')
        )
        if resultados.get('reacoes_elasticas'):
            legenda_handles.append(
                Line2D([0], [0], color='#D35400', linewidth=2, marker='>', markersize=5, label='Reações elásticas')
            )
    if estado['N']:
        legenda_handles.append(
            Line2D([0], [0], color=cores_diag['N'], linewidth=2, label='Normal (N)')
        )
    if estado['V']:
        legenda_handles.append(
            Line2D([0], [0], color=cores_diag['V'], linewidth=2, label='Cortante (V)')
        )
    if estado['M']:
        legenda_handles.append(
            Line2D([0], [0], color=cores_diag['M'], linewidth=2, label='Fletor (M)')
        )
    ax.legend(handles=legenda_handles, loc='upper left', fontsize=9, framealpha=0.9, edgecolor='#cccccc')


# =========================================================================
# WXPYTHON GUI CLASSES
# =========================================================================

class VisualizadorFrame(wx.Frame):
    def __init__(self, resultados, parent=None, title="Visualizador de Pórticos Planos - MEF"):
        # Obter tamanho do monitor para definir tamanho proporcional (evita ocultar barra de título em telas menores)
        display_w, display_h = wx.GetDisplaySize()
        win_w = min(1280, int(display_w * 0.85))
        win_h = min(768, int(display_h * 0.85))
        
        super().__init__(parent, title=title, size=(win_w, win_h), style=wx.DEFAULT_FRAME_STYLE)
        self.resultados = resultados
        
        # Centralizar a janela
        self.Centre()
        
        # Cores e Fontes
        self.SetBackgroundColour(wx.Colour(248, 249, 250))
        
        # Obter fatores de escala base
        self.fator_deformada_base = calcular_fator_escala(resultados, percentual=0.12)
        self.fator_N_base = _calcular_fator_escala_diagrama(resultados, 'N')
        self.fator_V_base = _calcular_fator_escala_diagrama(resultados, 'V')
        self.fator_M_base = _calcular_fator_escala_diagrama(resultados, 'M')
        
        # Escala inicial em porcentagem (100% = escala base)
        self.escala_deformada_pct = 100
        self.escala_diagramas_pct = 100
        
        # Estados
        self.estado = {
            'N': False,
            'V': False,
            'M': False,
            'delta': True,
            'R': False,
            'F': False,
        }
        self.estado_eq = {
            'N': False,
            'V': False,
            'M': False,
            'delta': False,
        }
        
        # Flag de zoom (para preservar zoom do usuário após a primeira plotagem)
        self.preserve_zoom = False
        
        # Inicializar atributos de seleção interativa
        self.selection_active = False
        self.selection_type = None
        self.selection_id = None
        self.selection_coords = None
        self.selection_x_local = None
        self.selection_Ux = None
        self.selection_Uy = None
        self.selection_Rz = None
        
        # Layout principal
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Sidebar
        sidebar = wx.Panel(self)
        sidebar.SetBackgroundColour(wx.Colour(245, 246, 248))
        sidebar_sizer = wx.BoxSizer(wx.VERTICAL)
        sidebar.SetSizer(sidebar_sizer)
        
        # Estilos de Fontes
        font_padrao = wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        font_bold = wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_titulo = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        
        # Título
        title_lbl = wx.StaticText(sidebar, label="Painel de Controle")
        title_lbl.SetFont(font_titulo)
        title_lbl.SetForegroundColour(wx.Colour(44, 62, 80))
        sidebar_sizer.Add(title_lbl, 0, wx.ALL | wx.ALIGN_LEFT, 15)
        
        sidebar_sizer.Add(wx.StaticLine(sidebar), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(15)
        
        # --- Grupo: Visualizações ---
        vis_lbl = wx.StaticText(sidebar, label="Camadas / Esforços")
        vis_lbl.SetFont(font_bold)
        vis_lbl.SetForegroundColour(wx.Colour(52, 73, 94))
        sidebar_sizer.Add(vis_lbl, 0, wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(10)
        
        # Grid para Toggles
        grid_sizer = wx.FlexGridSizer(rows=6, cols=2, vgap=8, hgap=15)
        
        self.cb_delta = wx.CheckBox(sidebar, label="Deformada (δ)")
        self.cb_delta.SetValue(self.estado['delta'])
        self.cb_delta.SetFont(font_bold)
        self.cb_delta.SetForegroundColour(wx.Colour(231, 76, 60))
        self.cb_delta_eq = wx.CheckBox(sidebar, label="Equações")
        self.cb_delta_eq.SetValue(self.estado_eq['delta'])
        self.cb_delta_eq.SetFont(font_padrao)
        
        self.cb_N = wx.CheckBox(sidebar, label="Normal (N)")
        self.cb_N.SetValue(self.estado['N'])
        self.cb_N.SetFont(font_bold)
        self.cb_N.SetForegroundColour(wx.Colour(21, 101, 192))
        self.cb_N_eq = wx.CheckBox(sidebar, label="Equações")
        self.cb_N_eq.SetValue(self.estado_eq['N'])
        self.cb_N_eq.SetFont(font_padrao)
        
        self.cb_V = wx.CheckBox(sidebar, label="Cortante (V)")
        self.cb_V.SetValue(self.estado['V'])
        self.cb_V.SetFont(font_bold)
        self.cb_V.SetForegroundColour(wx.Colour(230, 81, 0))
        self.cb_V_eq = wx.CheckBox(sidebar, label="Equações")
        self.cb_V_eq.SetValue(self.estado_eq['V'])
        self.cb_V_eq.SetFont(font_padrao)
        
        self.cb_M = wx.CheckBox(sidebar, label="Fletor (M)")
        self.cb_M.SetValue(self.estado['M'])
        self.cb_M.SetFont(font_bold)
        self.cb_M.SetForegroundColour(wx.Colour(106, 27, 154))
        self.cb_M_eq = wx.CheckBox(sidebar, label="Equações")
        self.cb_M_eq.SetValue(self.estado_eq['M'])
        self.cb_M_eq.SetFont(font_padrao)
        
        self.cb_F = wx.CheckBox(sidebar, label="Cargas (F)")
        self.cb_F.SetValue(self.estado['F'])
        self.cb_F.SetFont(font_bold)
        self.cb_F.SetForegroundColour(wx.Colour(0, 102, 204))
        
        self.cb_R = wx.CheckBox(sidebar, label="Reações (R)")
        self.cb_R.SetValue(self.estado['R'])
        self.cb_R.SetFont(font_bold)
        self.cb_R.SetForegroundColour(wx.Colour(34, 139, 34))
        
        grid_sizer.Add(self.cb_delta, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_delta_eq, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_N, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_N_eq, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_V, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_V_eq, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_M, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_M_eq, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.cb_F, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add((0, 0))
        grid_sizer.Add(self.cb_R, 0, wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add((0, 0))
        
        sidebar_sizer.Add(grid_sizer, 0, wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(15)
        
        sidebar_sizer.Add(wx.StaticLine(sidebar), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(15)
        
        # --- Grupo: Escalas ---
        esc_lbl = wx.StaticText(sidebar, label="Controle de Escala")
        esc_lbl.SetFont(font_bold)
        esc_lbl.SetForegroundColour(wx.Colour(52, 73, 94))
        sidebar_sizer.Add(esc_lbl, 0, wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(10)
        
        self.lbl_def = wx.StaticText(sidebar, label="Escala Deformada: 100%")
        self.lbl_def.SetFont(font_padrao)
        sidebar_sizer.Add(self.lbl_def, 0, wx.LEFT | wx.RIGHT, 15)
        
        self.slider_def = wx.Slider(sidebar, value=100, minValue=0, maxValue=500, style=wx.SL_HORIZONTAL)
        sidebar_sizer.Add(self.slider_def, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(10)
        
        self.lbl_diag = wx.StaticText(sidebar, label="Escala Diagramas: 100%")
        self.lbl_diag.SetFont(font_padrao)
        sidebar_sizer.Add(self.lbl_diag, 0, wx.LEFT | wx.RIGHT, 15)
        
        self.slider_diag = wx.Slider(sidebar, value=100, minValue=0, maxValue=500, style=wx.SL_HORIZONTAL)
        sidebar_sizer.Add(self.slider_diag, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(15)
        
        sidebar_sizer.Add(wx.StaticLine(sidebar), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(15)
        
        # --- Grupo: Informações do Ponto Selecionado ---
        self.selection_panel = wx.Panel(sidebar)
        self.selection_panel.SetBackgroundColour(wx.Colour(235, 240, 245))
        sel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.selection_panel.SetSizer(sel_sizer)
        
        sel_lbl = wx.StaticText(self.selection_panel, label="Informações de Seleção")
        sel_lbl.SetFont(font_bold)
        sel_lbl.SetForegroundColour(wx.Colour(44, 62, 80))
        sel_sizer.Add(sel_lbl, 0, wx.ALL | wx.ALIGN_LEFT, 8)
        
        self.txt_sel_tipo = wx.StaticText(self.selection_panel, label="Clique na estrutura para selecionar")
        self.txt_sel_tipo.SetFont(font_bold)
        self.txt_sel_tipo.SetForegroundColour(wx.Colour(52, 73, 94))
        sel_sizer.Add(self.txt_sel_tipo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        
        self.txt_sel_pos = wx.StaticText(self.selection_panel, label="Posição: -")
        self.txt_sel_pos.SetFont(font_padrao)
        sel_sizer.Add(self.txt_sel_pos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        
        self.txt_sel_ux = wx.StaticText(self.selection_panel, label="Desl. X (ux): -")
        self.txt_sel_ux.SetFont(font_padrao)
        sel_sizer.Add(self.txt_sel_ux, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        
        self.txt_sel_uy = wx.StaticText(self.selection_panel, label="Desl. Y (uy): -")
        self.txt_sel_uy.SetFont(font_padrao)
        sel_sizer.Add(self.txt_sel_uy, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        
        self.txt_sel_rz = wx.StaticText(self.selection_panel, label="Rotação (θz): -")
        self.txt_sel_rz.SetFont(font_padrao)
        sel_sizer.Add(self.txt_sel_rz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        
        self.btn_clear_sel = wx.Button(self.selection_panel, label="Limpar Seleção")
        self.btn_clear_sel.SetFont(font_padrao)
        self.btn_clear_sel.Disable()
        self.btn_clear_sel.Bind(wx.EVT_BUTTON, self.on_clear_selection)
        sel_sizer.Add(self.btn_clear_sel, 0, wx.ALL | wx.EXPAND, 8)
        
        sidebar_sizer.Add(self.selection_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(20)
        
        # --- Grupo: Ações ---
        actions_lbl = wx.StaticText(sidebar, label="Ações")
        actions_lbl.SetFont(font_bold)
        actions_lbl.SetForegroundColour(wx.Colour(52, 73, 94))
        sidebar_sizer.Add(actions_lbl, 0, wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(10)
        
        self.btn_fit = wx.Button(sidebar, label="Enquadrar Vista")
        self.btn_fit.SetFont(font_bold)
        self.btn_fit.SetBackgroundColour(wx.Colour(41, 128, 185))
        self.btn_fit.SetForegroundColour(wx.WHITE)
        sidebar_sizer.Add(self.btn_fit, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        sidebar_sizer.AddSpacer(10)
        
        self.btn_exit = wx.Button(sidebar, label="Sair")
        self.btn_exit.SetFont(font_bold)
        self.btn_exit.SetBackgroundColour(wx.Colour(192, 57, 43))
        self.btn_exit.SetForegroundColour(wx.WHITE)
        sidebar_sizer.Add(self.btn_exit, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        
        sidebar_sizer.Layout()
        
        # Canvas de Desenho (Direita)
        right_panel = wx.Panel(self)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel.SetSizer(right_sizer)
        
        self.fig = Figure(figsize=(10, 8), facecolor='#ffffff')
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(right_panel, -1, self.fig)
        right_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)
        
        # Barra de ferramentas
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()
        right_sizer.Add(self.toolbar, 0, wx.EXPAND | wx.ALL, 5)
        
        right_panel.Layout()
        
        # Adicionar painéis ao Frame principal
        main_sizer.Add(sidebar, 0, wx.EXPAND)
        main_sizer.Add(right_panel, 1, wx.EXPAND)
        self.SetSizer(main_sizer)
        
        # Binds
        self.cb_delta.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_delta_eq.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_N.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_N_eq.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_V.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_V_eq.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_M.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_M_eq.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_F.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        self.cb_R.Bind(wx.EVT_CHECKBOX, self.on_check_update)
        
        self.slider_def.Bind(wx.EVT_SLIDER, self.on_slider_def)
        self.slider_diag.Bind(wx.EVT_SLIDER, self.on_slider_diag)
        
        self.btn_fit.Bind(wx.EVT_BUTTON, self.on_fit_view)
        self.btn_exit.Bind(wx.EVT_BUTTON, self.on_exit)
        
        # Bind do clique do mouse no canvas do matplotlib
        self.canvas.mpl_connect('button_press_event', self.on_canvas_click)
        
        # Desenhar primeira vez
        self.atualizar_grafico()
        
    def on_check_update(self, event):
        self.atualizar_grafico()
        
    def on_slider_def(self, event):
        self.escala_deformada_pct = self.slider_def.GetValue()
        self.lbl_def.SetLabel(f"Escala Deformada: {self.escala_deformada_pct}%")
        self.atualizar_grafico()
        
    def on_slider_diag(self, event):
        self.escala_diagramas_pct = self.slider_diag.GetValue()
        self.lbl_diag.SetLabel(f"Escala Diagramas: {self.escala_diagramas_pct}%")
        self.atualizar_grafico()
        
    def on_fit_view(self, event):
        self.preserve_zoom = False
        self.atualizar_grafico()
        
    def on_exit(self, event):
        self.Close()
        
    def atualizar_grafico(self):
        # Capturar zoom atual antes do clear
        xlim = None
        ylim = None
        if self.preserve_zoom:
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
        # Sincronizar dicionários com os controles da GUI
        self.estado['delta'] = self.cb_delta.IsChecked()
        self.estado_eq['delta'] = self.cb_delta_eq.IsChecked()
        self.estado['N'] = self.cb_N.IsChecked()
        self.estado_eq['N'] = self.cb_N_eq.IsChecked()
        self.estado['V'] = self.cb_V.IsChecked()
        self.estado_eq['V'] = self.cb_V_eq.IsChecked()
        self.estado['M'] = self.cb_M.IsChecked()
        self.estado_eq['M'] = self.cb_M_eq.IsChecked()
        self.estado['F'] = self.cb_F.IsChecked()
        self.estado['R'] = self.cb_R.IsChecked()
        
        # Ativar ou desativar os sub-checkboxes de equações
        self.cb_delta_eq.Enable(self.estado['delta'])
        self.cb_N_eq.Enable(self.estado['N'])
        self.cb_V_eq.Enable(self.estado['V'])
        self.cb_M_eq.Enable(self.estado['M'])
        
        # Fatores numéricos ponderados pelos sliders
        fat_def = self.fator_deformada_base * (self.escala_deformada_pct / 100.0)
        fat_N = self.fator_N_base * (self.escala_diagramas_pct / 100.0)
        fat_V = self.fator_V_base * (self.escala_diagramas_pct / 100.0)
        fat_M = self.fator_M_base * (self.escala_diagramas_pct / 100.0)
        
        self.ax.clear()
        
        # Desenhar todos os elementos e esforços selecionados
        desenhar_grafico(
            self.ax,
            self.resultados,
            self.estado,
            self.estado_eq,
            fat_def,
            fat_N,
            fat_V,
            fat_M
        )        
        # Desenhar seleção ativa se houver
        if self.selection_active:
            sx, sy = self.selection_coords
            self.ax.plot(sx, sy, 'o', color='#F1C40F', markersize=10, zorder=20, markeredgecolor='black', markeredgewidth=1.0)
            self.ax.plot(sx, sy, 'o', color='#E74C3C', markersize=6, zorder=21)
            
            if self.selection_type == 'no':
                lbl_txt = f"Nó {self.selection_id}\n"
            else:
                lbl_txt = f"Elem. {self.selection_id}\nx = {self.selection_x_local:.2f} m\n"
            lbl_txt += f"Ux: {self.selection_Ux * 1000:.4f} mm\n"
            lbl_txt += f"Uy: {self.selection_Uy * 1000:.4f} mm\n"
            lbl_txt += f"Rot: {self.selection_Rz:.6f} rad"
            
            self.ax.annotate(
                lbl_txt,
                xy=(sx, sy),
                xytext=(15, 15),
                textcoords='offset points',
                arrowprops=dict(arrowstyle="->", color='#2C3E50', lw=1.2, connectionstyle="arc3,rad=0.1"),
                bbox=dict(boxstyle="round,pad=0.3", facecolor='#FBFBFB', edgecolor='#2C3E50', lw=1.0, alpha=0.95),
                fontsize=8,
                fontweight='bold',
                color='#2C3E50',
                zorder=22
            )
            
        # Definir limites de exibição
        if self.preserve_zoom and xlim is not None and ylim is not None:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)
        else:
            nos = self.resultados['nos']
            deslocamentos = self.resultados['deslocamentos']
            
            all_x = [c[0] for c in nos.values()]
            all_y = [c[1] for c in nos.values()]
            for no_id in nos:
                desl = deslocamentos[no_id]
                all_x.append(nos[no_id][0] + desl[0] * fat_def)
                all_y.append(nos[no_id][1] + desl[1] * fat_def)
 
            margem_x = max(1.0, (max(all_x) - min(all_x)) * 0.15)
            margem_y = max(1.0, (max(all_y) - min(all_y)) * 0.20)
            self.ax.set_xlim(min(all_x) - margem_x, max(all_x) + margem_x)
            self.ax.set_ylim(min(all_y) - margem_y, max(all_y) + margem_y)
            
            # Subsequentes atualizações reterão o zoom
            self.preserve_zoom = True
            
        self.canvas.draw()

    def on_canvas_click(self, event):
        # Ignorar cliques fora do gráfico ou se alguma ferramenta do toolbar (zoom/pan) estiver ativa
        if event.inaxes != self.ax or self.toolbar.mode != '':
            return
            
        x_c = event.xdata
        y_c = event.ydata
        
        nos = self.resultados['nos']
        elementos = self.resultados['elementos']
        deslocamentos = self.resultados['deslocamentos']
        diagramas = self.resultados.get('diagramas', {})
        
        # Calcular dimensões para definir raios de snap
        xs = [coord[0] for coord in nos.values()]
        ys = [coord[1] for coord in nos.values()]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        dim_max = max(dx, dy, 1.0)
        
        # Raios de snap (proporcionais ao tamanho do pórtico)
        r_snap_no = 0.04 * dim_max
        r_snap_barra = 0.03 * dim_max
        
        # Fator de escala da deformada usado no plot
        fat_def = self.fator_deformada_base * (self.escala_deformada_pct / 100.0)
        deformada_ativa = self.cb_delta.IsChecked()
        
        # 1. Verificar nós (original e deformado)
        closest_no = None
        min_dist_no = float('inf')
        snap_to_deformed_no = False
        
        for no_id, coord in nos.items():
            # Original
            dist_orig = np.sqrt((x_c - coord[0])**2 + (y_c - coord[1])**2)
            if dist_orig < min_dist_no:
                min_dist_no = dist_orig
                closest_no = no_id
                snap_to_deformed_no = False
                
            # Deformado (se ativo)
            if deformada_ativa:
                desl = deslocamentos[no_id]
                xd = coord[0] + desl[0] * fat_def
                yd = coord[1] + desl[1] * fat_def
                dist_def = np.sqrt((x_c - xd)**2 + (y_c - yd)**2)
                if dist_def < min_dist_no:
                    min_dist_no = dist_def
                    closest_no = no_id
                    snap_to_deformed_no = True
                    
        # 2. Verificar barras (original e deformada)
        closest_elem = None
        closest_x_local = None
        closest_pt_plot = None
        min_dist_elem = float('inf')
        snap_to_deformed_elem = False
        
        for elem_id, elem in elementos.items():
            ni = str(elem['ni'])
            nj = str(elem['nj'])
            x1, y1 = nos[ni]
            x2, y2 = nos[nj]
            L = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            if L < 1e-12:
                continue
            cos_a = (x2 - x1) / L
            sin_a = (y2 - y1) / L
            
            # --- Checar deformada (se ativa) ---
            diag = diagramas.get(str(elem_id), {})
            def_info = diag.get('deformada', {})
            if deformada_ativa and def_info:
                xs_loc = def_info.get('xs', [])
                us_vals = def_info.get('us', [])
                vs_vals = def_info.get('vs', [])
                
                # Gerar os pontos plotados
                pts_def_x = []
                pts_def_y = []
                for xl, u_val, v_val in zip(xs_loc, us_vals, vs_vals):
                    bx = x1 + xl * cos_a
                    by = y1 + xl * sin_a
                    xd = bx + fat_def * (u_val * cos_a - v_val * sin_a)
                    yd = by + fat_def * (u_val * sin_a + v_val * cos_a)
                    pts_def_x.append(xd)
                    pts_def_y.append(yd)
                
                # Encontrar segmento mais próximo na linha poligonal da deformada
                for i in range(len(pts_def_x) - 1):
                    px1, py1 = pts_def_x[i], pts_def_y[i]
                    px2, py2 = pts_def_x[i+1], pts_def_y[i+1]
                    lx = px2 - px1
                    ly = py2 - py1
                    l_seg = np.sqrt(lx**2 + ly**2)
                    if l_seg < 1e-12:
                        continue
                    
                    # Projeção no segmento
                    t_proj = ((x_c - px1) * lx + (y_c - py1) * ly) / (l_seg**2)
                    t_clamped = max(0.0, min(1.0, t_proj))
                    
                    qx = px1 + t_clamped * lx
                    qy = py1 + t_clamped * ly
                    dist = np.sqrt((x_c - qx)**2 + (y_c - qy)**2)
                    
                    if dist < min_dist_elem:
                        min_dist_elem = dist
                        closest_elem = elem_id
                        # Interpolação linear da coordenada local x correspondente
                        closest_x_local = xs_loc[i] + t_clamped * (xs_loc[i+1] - xs_loc[i])
                        closest_pt_plot = (qx, qy)
                        snap_to_deformed_elem = True
            
            # --- Checar geometria original ---
            wx = x_c - x1
            wy = y_c - y1
            x_proj = wx * cos_a + wy * sin_a
            x_clamped = max(0.0, min(L, x_proj))
            qx = x1 + x_clamped * cos_a
            qy = y1 + x_clamped * sin_a
            dist_orig = np.sqrt((x_c - qx)**2 + (y_c - qy)**2)
            
            if dist_orig < min_dist_elem:
                min_dist_elem = dist_orig
                closest_elem = elem_id
                closest_x_local = x_clamped
                closest_pt_plot = (qx, qy)
                snap_to_deformed_elem = False

        # 3. Decisão da Seleção (Prioridade ao Nó)
        self.selection_active = False
        
        if min_dist_no < r_snap_no:
            # Snapped to a node!
            self.selection_active = True
            self.selection_type = 'no'
            self.selection_id = closest_no
            coord = nos[closest_no]
            
            # Posição do marcador no plot
            if snap_to_deformed_no and deformada_ativa:
                desl = deslocamentos[closest_no]
                self.selection_coords = (coord[0] + desl[0] * fat_def, coord[1] + desl[1] * fat_def)
            else:
                self.selection_coords = (coord[0], coord[1])
                
            # Deslocamentos
            Ux, Uy, Rz = deslocamentos[closest_no]
            self.selection_Ux = Ux
            self.selection_Uy = Uy
            self.selection_Rz = Rz
            
        elif min_dist_elem < r_snap_barra:
            # Snapped to an element!
            self.selection_active = True
            self.selection_type = 'barra'
            self.selection_id = closest_elem
            self.selection_coords = closest_pt_plot
            self.selection_x_local = closest_x_local
            
            diag = diagramas.get(str(closest_elem), {})
            L = diag.get('L', 1.0)
            cos_a = diag.get('cos', 1.0)
            sin_a = diag.get('sin', 0.0)
            
            def_info = diag.get('deformada', {})
            if def_info:
                coefs_u = def_info.get('coefs_u')
                coefs_v = def_info.get('coefs_v')
                coefs_theta = def_info.get('coefs_theta')
                E = def_info.get('E')
                A = def_info.get('A')
                Iz = def_info.get('Iz')
                
                # Avaliar polinômios
                x = closest_x_local
                ux_local = sum(c * (x**i) for i, c in enumerate(coefs_u)) / (E * A)
                uy_local = sum(c * (x**i) for i, c in enumerate(coefs_v)) / (E * Iz)
                theta_z = sum(c * (x**i) for i, c in enumerate(coefs_theta)) / (E * Iz)
                
                # Rotacionar para global
                Ux = ux_local * cos_a - uy_local * sin_a
                Uy = ux_local * sin_a + uy_local * cos_a
                Rz = theta_z
            else:
                # Interpolação linear fallback
                ni = str(elementos[closest_elem]['ni'])
                nj = str(elementos[closest_elem]['nj'])
                u_i = deslocamentos[ni]
                u_j = deslocamentos[nj]
                t = closest_x_local / L
                Ux = (1 - t) * u_i[0] + t * u_j[0]
                Uy = (1 - t) * u_i[1] + t * u_j[1]
                Rz = (1 - t) * u_i[2] + t * u_j[2]
                
            self.selection_Ux = Ux
            self.selection_Uy = Uy
            self.selection_Rz = Rz

        if self.selection_active:
            # Habilitar botão de limpar
            self.btn_clear_sel.Enable(True)
            self.atualizar_sidebar_selecao()
        else:
            # Não clicou em nada próximo
            self.on_clear_selection(None)
            
        # Redesenhar para atualizar marker e callout
        self.atualizar_grafico()

    def atualizar_sidebar_selecao(self):
        if not self.selection_active:
            return
            
        if self.selection_type == 'no':
            self.txt_sel_tipo.SetLabel(f"Nó Selecionado: {self.selection_id}")
            # Posição original do nó
            coord = self.resultados['nos'][self.selection_id]
            self.txt_sel_pos.SetLabel(f"Posição: X={coord[0]:.3f} m, Y={coord[1]:.3f} m")
        else:
            diag = self.resultados['diagramas'].get(str(self.selection_id), {})
            L = diag.get('L', 0.0)
            self.txt_sel_tipo.SetLabel(f"Elemento: E{self.selection_id}")
            self.txt_sel_pos.SetLabel(f"Trecho: x={self.selection_x_local:.3f} m de {L:.3f} m")
            
        # Exibir deslocamentos
        self.txt_sel_ux.SetLabel(f"Desl. X (ux): {self.selection_Ux * 1000:.4f} mm")
        self.txt_sel_uy.SetLabel(f"Desl. Y (uy): {self.selection_Uy * 1000:.4f} mm")
        
        # Exibir rotação em radianos e graus
        rot_graus = np.degrees(self.selection_Rz)
        self.txt_sel_rz.SetLabel(f"Rotação (θz): {self.selection_Rz:.6f} rad ({rot_graus:.4f}°)")
        
        # Ajustar tamanho do painel se necessário
        self.selection_panel.Layout()

    def on_clear_selection(self, event):
        self.selection_active = False
        self.selection_type = None
        self.selection_id = None
        self.selection_coords = None
        self.selection_x_local = None
        
        self.txt_sel_tipo.SetLabel("Clique na estrutura para selecionar")
        self.txt_sel_pos.SetLabel("Posição: -")
        self.txt_sel_ux.SetLabel("Desl. X (ux): -")
        self.txt_sel_uy.SetLabel("Desl. Y (uy): -")
        self.txt_sel_rz.SetLabel("Rotação (θz): -")
        
        self.btn_clear_sel.Disable()
        self.selection_panel.Layout()
        
        self.atualizar_grafico()


def plotar_portico(resultados, fator_escala=None):
    """
    Interface para abrir o aplicativo de visualização com wxPython.
    """
    app = wx.App(False)
    frame = VisualizadorFrame(resultados)
    frame.Show()
    app.MainLoop()


# =========================================================================
# 8. IMPRESSÃO DOS RESULTADOS (opcional)
# =========================================================================

def imprimir_resumo(resultados):
    """Imprime um resumo dos resultados carregados do JSON."""
    deslocamentos = resultados['deslocamentos']
    reacoes = resultados['reacoes']

    print("\n" + "=" * 57)
    print("  RESUMO DOS RESULTADOS")
    print("=" * 57)

    print("\nDeslocamentos nodais:")
    print(f"{'Nó':>5}{'Desl.x':>16}{'Desl.y':>16}{'Rot.z':>18}")
    print("-" * 57)
    for no_id in sorted(deslocamentos.keys(), key=int):
        d = deslocamentos[no_id]
        print(f"{no_id:>5}{d[0]:>16.8f}{d[1]:>16.8f}{d[2]:>18.8f}")

    print("\nReações de apoio:")
    print(f"{'Nó':>5}{'Dir.':>6}{'Esforço':>16}")
    print("-" * 33)
    for r in reacoes:
        print(f"{r['no']:>5}{r['dir']:>6}{r['valor']:>16.4f}")

    # Imprimir equações dos diagramas (se disponíveis)
    diagramas = resultados.get('diagramas', {})
    if diagramas:
        print("\n" + "=" * 57)
        print("  EQUAÇÕES DOS ESFORÇOS E DEFORMAÇÕES (por elemento)")
        print("=" * 57)
        for elem_id in sorted(diagramas.keys(), key=int):
            diag = diagramas[elem_id]
            eq_textos = diag.get('equacoes_texto', {})
            print(f"\n  Elemento {elem_id} (L = {diag['L']:.4f} m):")
            for tipo in ['N', 'V', 'M']:
                if tipo in eq_textos:
                    print(f"    {eq_textos[tipo]}")
            
            # Imprimir equações da deformada
            def_info = diag.get('deformada', {})
            if def_info:
                eq_u = def_info.get('eq_u', '')
                eq_v = def_info.get('eq_v', '')
                if eq_v:
                    print(f"    {eq_v}")
                if eq_u:
                    print(f"    {eq_u}")


# =========================================================================
# PROGRAMA PRINCIPAL
# =========================================================================

def main():
    if len(sys.argv) < 2:
        print("Uso: python visualizacao.py <arquivo_resultados.json>")
        print("Exemplo: python visualizacao.py resultados.json")
        sys.exit(1)

    arquivo = sys.argv[1]

    if not os.path.exists(arquivo):
        print(f"Erro: arquivo '{arquivo}' não encontrado.")
        sys.exit(1)

    print(f">>> Carregando resultados de: {arquivo}")
    resultados = carregar_resultados(arquivo)

    # Imprimir resumo
    imprimir_resumo(resultados)

    # Plotar
    print("\n>>> Gerando visualização gráfica...")
    plotar_portico(resultados)


if __name__ == '__main__':
    main()
