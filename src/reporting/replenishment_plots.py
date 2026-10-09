"""Ten descriptive figures from Phase 8 outputs; no analytical calibration here."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from src.replenishment.simulation import FOLDER
from src.reporting.demand_understanding_plots import finish

ORDER = ["LEAN", "BASE", "PROTECTED"]
COLORS = ["#26828e", "#31688e", "#6c4b9a"]
NOTE = "Simulação hipotética • venda observada normalizada • sem quantidade de compra"


def subset(data, stage="final_snapshot", level="global"):
    return data["summary"].loc[lambda x: x.stage.eq(stage) & x.level.eq(level)]


def complete(fig, title, subtitle=NOTE):
    finish(fig, title, subtitle)
    return fig


def coverage(data):
    d = subset(data, "validation_fold4").set_index("scenario").loc[ORDER]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(3)
    ax.bar(x - .18, d.observed_coverage_rate, .36, label="Empírico (regra fixa)", color=COLORS[0])
    ax.bar(x + .18, d.normal_coverage_rate, .36, label="Normal (referência)", color=COLORS[2])
    ax.scatter(x, d.target_coverage_level, marker="_", s=800, color="black", label="Alvo hipotético", zorder=4)
    for i, value in enumerate(d.observed_coverage_rate):
        ax.text(i - .18, value + .005, f"{value:.2%}", ha="center", fontsize=10)
    ax.set(xticks=x, xticklabels=ORDER, ylim=(.70, 1.03), ylabel="Séries com ROP ≥ venda acumulada")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.legend(loc="lower right")
    return complete(fig, "1. Cobertura temporal: folds 1–3 → fold 4", "Alvo é referência histórica; não representa nível de serviço real ou garantia futura.")


def multipliers(data):
    d = data["simulation"]
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, name in enumerate(ORDER):
        group = d.loc[d.scenario.eq(name)]
        ax.boxplot(group.empirical_multiplier, positions=[i], widths=.5, showfliers=False,
                   patch_artist=True, boxprops={"facecolor": COLORS[i], "alpha": .6})
        ax.scatter(i, group.theoretical_normal_z.iloc[0], marker="D", color="black", zorder=4)
    ax.plot([], [], "D", color="black", label="z Normal")
    ax.set(xticks=range(3), xticklabels=ORDER, ylabel="Multiplicador final aplicado por série")
    ax.legend()
    return complete(fig, "2. Quantis empíricos finais vs referência Normal", "Caixas ponderadas por séries; quatro folds de train. Pontos extremos omitidos somente no gráfico.")


def distribution(data, column, title):
    fig, ax = plt.subplots(figsize=(10, 5))
    d = data["simulation"]
    values = [d.loc[d.scenario.eq(name), column].to_numpy() for name in ORDER]
    ax.boxplot(values, tick_labels=ORDER, showfliers=False, patch_artist=True,
               boxprops={"facecolor": COLORS[0], "alpha": .6})
    ax.set(ylabel="Escala normalizada (não unidades físicas)", yscale="symlog", ylim=(0, None))
    return complete(fig, title, "Escala vertical symlog; pontos extremos omitidos apenas na figura. Estatísticas completas no mart.")


def safety(data):
    return distribution(data, "safety_stock", "3. Safety stock simulado por cenário")


def reorder(data):
    return distribution(data, "reorder_point", "4. Reorder point simulado por cenário")


def grouped(data, level, value, title, ylabel):
    d = subset(data, level=level)
    cells = sorted(d.cell.unique())
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(cells))
    for i, name in enumerate(ORDER):
        group = d.loc[d.scenario.eq(name)].set_index("cell").reindex(cells)
        ax.bar(x + (i - 1) * .25, group[value], .25, label=name, color=COLORS[i])
    ax.set(xticks=x, xticklabels=cells, ylabel=ylabel)
    ax.legend()
    return complete(fig, title)


def abc(data):
    fig = grouped(data, "ABC", "median_buffer_ratio", "5. Buffer / forecast por ABC", "Mediana dos ratios por série")
    fig.axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    return fig


def xyz(data):
    return grouped(data, "XYZ", "mean_safety_stock", "6. Buffer médio por XYZ", "Safety stock simulado médio")


def exposure(data):
    return grouped(data, "exposure", "mean_safety_stock", "7. Buffer médio por exposição à ruptura", "Safety stock simulado médio")


def risk(data):
    d = data["simulation"].loc[lambda x: x.abc_class.eq("A")]
    fig, ax = plt.subplots(figsize=(10, 5))
    names = ["NEITHER", "UNDERFORECAST_ONLY", "CENSORING_ONLY", "CENSORING_AND_UNDERFORECAST"]
    labels = ["Sem sinais", "Só subprevisão", "Só censura", "Duplo sinal"]
    for i, scenario in enumerate(ORDER):
        grouped_frame = d.loc[d.scenario.eq(scenario)].groupby("demand_observation_risk_cell").safety_stock.mean().reindex(names)
        ax.bar(np.arange(4) + (i - 1) * .25, grouped_frame, .25, label=scenario, color=COLORS[i])
    ax.set(xticks=range(4), xticklabels=labels, ylabel="Safety stock médio entre séries A")
    ax.legend()
    return complete(fig, "8. Séries A: buffers e sinais de observação", "706 séries A com duplo sinal: grupo de investigação. Flags não entram na fórmula.")


def fallback(data):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    levels = ["ABC_XYZ_EXPOSURE", "ABC_XYZ", "XYZ", "GLOBAL"]
    colors = [COLORS[0], COLORS[2], "#d58a32", "#a33b42"]
    for ax, stage, title in zip(axes, ["validation_fold4", "final_snapshot"], ["Validação fold 4", "Snapshot final"]):
        d = data["fallback_distribution"].loc[lambda x: x.stage.eq(stage)]
        matrix = d.pivot(index="scenario", columns="calibration_level_used", values="n_series").reindex(index=ORDER, columns=levels).fillna(0) / 50000
        base = np.zeros(3)
        for level, color in zip(levels, colors):
            ax.bar(ORDER, matrix[level], bottom=base, label=level, color=color)
            base += matrix[level].to_numpy()
        ax.set(title=title, ylabel="Participação das séries", ylim=(0, 1.05))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].legend(fontsize=8, loc="lower right")
    return complete(fig, "9. Hierarquia de calibração e fallback", "Escolha por suporte mínimo de cauda: 200 / 400 / 1.000 janelas; nenhuma seleção por performance.")


def examples(data):
    d = data["examples"]
    fig, axes = plt.subplots(2, 4, figsize=(14, 8))
    for ax, (_, group) in zip(axes.flat, d.groupby("selection_rule", sort=True)):
        group = group.set_index("scenario").loc[ORDER]
        ax.bar(range(3), group.lead_time_forecast, color=COLORS[0], label="Forecast L")
        ax.bar(range(3), group.safety_stock, bottom=group.lead_time_forecast, color=COLORS[2], label="Buffer")
        first = group.iloc[0]
        title = str(first.selection_rule).replace("A_CENSORING_AND_UNDERFORECAST", "A_DOUBLE_SIGNAL")
        ax.set(title=f"{title}\nLoja {first.store_id} / produto {first.product_id}", xticks=range(3),
               xticklabels=["L1/.90", "L2/.95", "L3/.98"], ylabel="ROP simulado")
        ax.title.set_fontsize(9)
    axes.flat[-1].axis("off")
    axes.flat[-1].legend(*axes.flat[0].get_legend_handles_labels(), loc="center")
    return complete(fig, "10. Sete exemplos congelados da Fase 6", "Escalas variam entre painéis. Soma das barras = limiar simulado, nunca quantidade de compra.")


PLOTS = [coverage, multipliers, safety, reorder, abc, xyz, exposure, risk, fallback, examples]


def save_figure(fig, index, root):
    folder = root / FOLDER / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / f"{index:02d}_replenishment.png", dpi=130, bbox_inches="tight")
