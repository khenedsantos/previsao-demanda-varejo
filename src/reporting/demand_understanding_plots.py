"""Nove figuras descritivas; leem somente outputs reproduzíveis da Fase 2."""

import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from src.ingestion.source_manifest import ROOT


BLUE = "#246A91"
ORANGE = "#C66132"
GREEN = "#278478"
WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def load_outputs(root=ROOT):
    folder = root / "data/outputs/demand_understanding"
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    return {"summary":summary,"profile":pd.read_parquet(root / summary["artifacts"]["profile"]["path"]),
            "concentration":pd.read_parquet(folder / "concentration.parquet"),
            "examples":pd.read_parquet(folder / "example_series.parquet")}


def finish(fig, title, subtitle):
    fig.suptitle(title, x=.04, ha="left", fontsize=16, fontweight="bold", color="#173447")
    fig.text(.04, .012, subtitle, fontsize=9, color="#455765")
    for axis in fig.axes:
        axis.spines[["top","right"]].set_visible(False)
        axis.grid(axis="y", alpha=.15)
        axis.set_axisbelow(True)
    fig.tight_layout(rect=(.025,.055,.98,.92))
    return fig


def empirical_cdf(axis, values, label, color=BLUE):
    values = np.sort(np.asarray(values.dropna()))
    if len(values):
        axis.step(values,np.arange(1,len(values)+1)/len(values),where="post",label=label,color=color)
    axis.yaxis.set_major_formatter(PercentFormatter(1))
    axis.set_ylabel("Parcela acumulada de séries")


def distribution(data):
    p = data["profile"]
    fig, axes = plt.subplots(1,2,figsize=(12,4.8))
    axes[0].hist(p.mean_demand,bins=np.geomspace(p.mean_demand.min(),p.mean_demand.max(),45),color=BLUE)
    axes[0].set(xscale="log",xlabel="Média diária da venda normalizada (escala log)",ylabel="Séries")
    axes[1].hist(p.coefficient_of_variation.dropna(),bins=50,color=GREEN)
    axes[1].set(xlabel="CV diário (desvio amostral / média)",ylabel="Séries")
    return finish(fig,"01 · Nível de venda e variabilidade diferem entre séries",
                  "Train · 50 mil séries · venda observada normalizada; CV não mede sozinho previsibilidade.")


def concentration(data):
    fig, axis = plt.subplots(figsize=(11,5.3))
    curves = data["concentration"]
    for level,label,color in [("product","Produtos",BLUE),("store","Lojas",GREEN),("series","Loja × produto",ORANGE)]:
        rows = curves.loc[curves.level==level]
        axis.plot(np.r_[0,rows.entity_fraction],np.r_[0,rows.cumulative_share],label=label,color=color,lw=2)
    axis.axhline(.8,color="#667680",ls="--",lw=1,label="80% da venda (referência)")
    axis.plot([0,1],[0,1],color="#bbc3c8",ls=":",label="Participação uniforme")
    axis.set(xlim=(0,1),ylim=(0,1.01),xlabel="Parcela de entidades, ordenadas por contribuição",ylabel="Participação acumulada na venda normalizada")
    axis.xaxis.set_major_formatter(PercentFormatter(1))
    axis.yaxis.set_major_formatter(PercentFormatter(1))
    axis.legend(loc="lower right")
    return finish(fig,"02 · A concentração depende do nível de análise",
                  "Contribuição de venda normalizada no painel observado · nenhuma classificação ABC aplicada.")


def intermittency(data):
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    p=data["profile"]
    empirical_cdf(axes[0],p.zero_ratio,"Zeros")
    axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_xlabel("Proporção de dias com venda zero")
    empirical_cdf(axes[1],p.adi,"ADI",GREEN)
    axes[1].set_xlabel("ADI = dias / dias positivos")
    return finish(fig,"03 · Zeros são pouco frequentes no agregado, com exceções",
                  "ADI e proporção de zeros são matematicamente redundantes nesta janela · nenhuma classe de intermitência.")


def weekday(data):
    d=pd.DataFrame(data["summary"]["weekday"])
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    axes[0].bar(WEEKDAYS,d.mean_demand,color=[BLUE]*5+[GREEN]*2)
    axes[0].set(ylabel="Venda normalizada média / dia",xlabel="Dia da semana")
    q=np.array(d.relative_series_quantiles.tolist())
    x=np.arange(7)
    axes[1].fill_between(x,q[:,0],q[:,2],alpha=.2,color=GREEN,label="p25–p75 das séries")
    axes[1].plot(x,q[:,1],marker="o",color=GREEN,label="Mediana das séries")
    axes[1].axhline(1,color="#667680",ls=":")
    axes[1].set(xticks=x,xticklabels=WEEKDAYS,ylabel="Média do weekday / média da própria série",xlabel="Dia da semana")
    axes[1].legend()
    return finish(fig,"04 · Fim de semana tem maior venda, com heterogeneidade",
                  "Médias corrigem as contagens diferentes de weekdays · faixa entre séries; não é intervalo de confiança.")


def weekly_stability(data):
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    p=data["profile"]
    axes[0].hist(p.autocorrelation_lag7.dropna(),bins=50,color=BLUE)
    axes[0].axvline(0,color="#667680",ls=":")
    axes[0].set(xlabel="Correlação Pearson entre t e t−7",ylabel="Séries")
    axes[1].hist(p.weekly_pattern_half_correlation.dropna(),bins=50,color=GREEN)
    axes[1].axvline(0,color="#667680",ls=":")
    axes[1].set(xlabel="Correlação do perfil semanal: primeira × segunda metade",ylabel="Séries")
    missing=p.weekly_pattern_half_correlation.isna().sum()
    return finish(fig,"05 · O padrão agregado não garante estabilidade por série",
                  f"12 semanas completas, duas metades de 6 · {missing} séries sem estabilidade válida · não são testes de significância.")


def availability(data):
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    axes[0].hist(data["profile"].stockout_rate,bins=30,color=ORANGE)
    axes[0].set(xlabel="Fração de dias com ruptura [06h,22h)",ylabel="Séries")
    axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    d=pd.DataFrame(data["summary"]["stockout_hours"])
    axes[1].bar(d.stockout_hours,d.n_rows/1e6,color=ORANGE)
    axes[1].set(xlabel="Horas com ruptura na janela operacional",ylabel="Registros (milhões)",xticks=[0,4,8,12,16])
    return finish(fig,"06 · Ruptura afeta todas as séries, em intensidades diferentes",
                  "Contador restrito a [06h,22h) · dias sem ruptura nessa janela não equivalem a disponibilidade de 24 horas.")


def paired_hexbin(axis, frame, x, y, xlabel, ylabel):
    valid=frame[[x,y]].dropna()
    grid=axis.hexbin(valid[x],valid[y],gridsize=45,mincnt=1,bins="log",cmap="YlGnBu",linewidths=0)
    maximum=valid.to_numpy().max()
    axis.plot([0,maximum],[0,maximum],color=ORANGE,ls="--",lw=1)
    axis.set(xlabel=xlabel,ylabel=ylabel)
    colorbar=axis.figure.colorbar(grid,ax=axis,pad=.02)
    colorbar.set_label("Séries por célula (cor log)")


def stockout_sales(data):
    fig,axes=plt.subplots(1,2,figsize=(12,5.2))
    paired_hexbin(axes[0],data["profile"],"mean_demand_without_stockout","mean_demand_with_stockout",
                  "Média da série sem ruptura","Média da mesma série com ruptura")
    d=pd.DataFrame(data["summary"]["stockout_hours"])
    axes[1].plot(d.stockout_hours,d.zero_ratio,marker="o",color=ORANGE)
    axes[1].set(xlabel="Horas de ruptura em [06h,22h)",ylabel="Proporção de venda zero",xticks=[0,4,8,12,16])
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    return finish(fig,"07 · Dias de ruptura total concentram zeros observados",
                  "Comparação pareada por série à esquerda; associação descritiva à direita · nenhuma estimativa de venda perdida.")


def promotions(data):
    fig,axes=plt.subplots(1,2,figsize=(12,5.2))
    paired_hexbin(axes[0],data["profile"],"mean_demand_without_activity","mean_demand_with_activity",
                  "Média da série sem atividade","Média da mesma série com atividade")
    d=pd.DataFrame(data["summary"]["discount_domains"])
    axes[1].step(d.discount,d.n_rows.cumsum()/d.n_rows.sum(),where="post",color=GREEN)
    axes[1].axvline(1,color=ORANGE,ls="--")
    axes[1].set(xlabel="Fator discount original",ylabel="Parcela acumulada de registros",xlim=(-.02,1.11))
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].text(.04,.78,"34 valores > 1\n16.039 valores = 0",transform=axes[1].transAxes,fontsize=10)
    return finish(fig,"08 · Atividade promocional e discount são sinais distintos",
                  "Extremos preservados · comparação dentro da série não controla seleção dos dias e não identifica uplift causal.")


def examples(data):
    fig,axes=plt.subplots(5,1,figsize=(12,13),sharex=True)
    daily=data["examples"]
    for axis,example in zip(axes,data["summary"]["examples"]):
        rows=daily.loc[daily.rule==example["rule"]].sort_values("dt")
        dates=pd.to_datetime(rows.dt)
        axis.plot(dates,rows.sale_amount,color=BLUE,lw=1.3,label="Venda observada normalizada")
        affected=rows.stock_hour6_22_cnt>0
        axis.scatter(dates[affected],rows.loc[affected,"sale_amount"],s=14,color=ORANGE,label="Dia com ruptura")
        axis.set_title(f"{example['rule'].replace('_',' ')} · loja {example['store_id']} / produto {example['product_id']}",loc="left",fontsize=11)
        axis.set_ylabel("Venda norm.")
        axis.set_ylim(bottom=0)
    axes[0].legend(loc="upper right",fontsize=8)
    axes[-1].xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axes[-1].set_xlabel("Data em train (2024)")
    return finish(fig,"09 · Exemplos escolhidos por regra, sem seleção visual",
                  "Quartis empíricos de venda/ruptura e máximos de CV/zeros · escalas verticais próprias · não são segmentos ABC/XYZ.")


PLOTS = [distribution,concentration,intermittency,weekday,weekly_stability,availability,stockout_sales,promotions,examples]


def save_figure(fig, number, root=ROOT):
    folder=root / "data/outputs/demand_understanding/figures"
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder / f"{number:02d}.png",dpi=140,facecolor="white")
