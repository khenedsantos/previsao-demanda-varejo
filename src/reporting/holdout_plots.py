"""Dez figuras de avaliação; somente outputs, sem ajuste ou acesso a raw."""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from src.reporting.demand_understanding_plots import finish, BLUE, GREEN, ORANGE
from src.forecasting.holdout import ROOT, FOLDER


NAMES={"ets_ana":"ETS A/N/A","seasonal_naive":"Seasonal Naive"}
COLORS={"ets_ana":ORANGE,"seasonal_naive":BLUE}
PERCENT={"wape","bias_pct","underforecast_rate"}
RISK=["NEITHER","UNDERFORECAST_ONLY","CENSORING_ONLY","CENSORING_AND_UNDERFORECAST"]
RISK_SHORT=["Nenhum dos dois","Só persistência","Só censura","Duplo sinal"]


def bars(ax,frame,dimension,order,metric,title,labels=None):
    x=np.arange(len(order))
    for i,model in enumerate(["seasonal_naive","ets_ana"]):
        values=frame.loc[frame.model.eq(model)].set_index(dimension).reindex(order)[metric]
        ax.bar(x+(i-.5)*.36,values,.34,color=COLORS[model],label=NAMES[model])
    ax.set(xticks=x,xticklabels=labels or [str(x) for x in order],title=title)
    if metric in PERCENT:
        ax.yaxis.set_major_formatter(PercentFormatter(1))
    if metric in {"bias","bias_pct"}:
        ax.axhline(0,color="#5c6870",lw=.8)


def global_metrics(d):
    frame=d["model_comparison"].loc[lambda x:x.level.eq("global")].copy()
    frame["group"]="Holdout"
    fig,axes=plt.subplots(1,3,figsize=(13,4.8))
    for ax,metric in zip(axes,["mae","rmse","wape"]):
        bars(ax,frame,"group",["Holdout"],metric,metric.upper())
    axes[0].legend(fontsize=9)
    return finish(fig,"01 · ETS versus Seasonal Naive no holdout","350.000 previsões por modelo · metodologia congelada antes de ler actuals · venda normalizada")


def temporal(d,metric,number):
    fig,ax=plt.subplots(figsize=(11,5))
    for model in ["seasonal_naive","ets_ana"]:
        part=d["backtest_folds"].loc[lambda x:x.model.eq(model)].sort_values("fold_id")
        final=d["model_comparison"].loc[lambda x:x.level.eq("global")&x.model.eq(model),metric].iloc[0]
        ax.plot(range(1,6),[*part[metric],final],marker="o",color=COLORS[model],label=NAMES[model])
    ax.axvline(4.5,color="#6b7880",ls="--",lw=1)
    ax.set(xticks=range(1,6),xticklabels=["Fold 1","Fold 2","Fold 3","Fold 4","Holdout"],ylabel=metric)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    if metric=="bias_pct":
        ax.axhline(0,color="#6b7880",lw=.8)
    ax.legend()
    return finish(fig,f"{number:02d} · {metric} nos quatro folds e no teste final","Janelas de sete dias · o intervalo observado nos folds não é intervalo de confiança")


def segment(d,level,dimension,order,number,title):
    frame=d["model_comparison"].loc[lambda x:x.level.eq(level)]
    fig,axes=plt.subplots(2,2,figsize=(12,7))
    for ax,metric in zip(axes.flat,["mae","rmse","wape","bias_pct"]):
        bars(ax,frame,dimension,order,metric,metric)
    axes[0,0].legend(fontsize=9)
    return finish(fig,f"{number:02d} · {title}","Labels conhecidos em 25/06 · nenhuma segmentação recalculada com eval")


def persistent(d):
    frame=d["model_comparison"].loc[lambda x:x.level.eq("persistent_underforecast_flag")]
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for ax,metric in zip(axes.flat,["mae","rmse","wape","bias","bias_pct","underforecast_rate"]):
        bars(ax,frame,"persistent_underforecast_flag",[False,True],metric,metric,["Não persistente","Persistente"])
    axes[0,0].legend(fontsize=8)
    retained=d["persistence_retention"].loc[lambda x:x.persistent_underforecast_flag].iloc[0]
    return finish(fig,"06 · Persistência histórica em avaliação prospectiva",
        f"16.529 séries definidas antes de eval · {retained.negative_holdout_bias_rate:.2%} mantêm bias negativo no holdout · sem mudar a regra")


def risk(d):
    frame=d["model_comparison"].loc[lambda x:x.level.eq("risk_cell")&x.model.eq("ets_ana")].set_index("demand_observation_risk_cell").reindex(RISK)
    fig,axes=plt.subplots(2,2,figsize=(13,7))
    for ax,metric in zip(axes.flat,["mae","rmse","bias_pct","underforecast_rate"]):
        ax.barh(RISK_SHORT,frame[metric],color=[BLUE,GREEN,"#a283ae",ORANGE])
        ax.set_title(metric)
        ax.invert_yaxis()
        if metric in PERCENT:
            ax.xaxis.set_major_formatter(PercentFormatter(1))
        if metric=="bias_pct":
            ax.axvline(0,color="#6b7880",lw=.8)
    return finish(fig,"07 · Os quatro grupos congelados no holdout ETS","Duplo sinal = possível censura histórica + persistência histórica · não comprova demanda perdida")


def priority(d):
    frame=d["model_comparison"].loc[lambda x:x.level.eq("a_double_signal")].copy()
    frame["group"]="706 séries A"
    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for ax,metric in zip(axes,["rmse","bias_pct","underforecast_rate"]):
        bars(ax,frame,"group",["706 séries A"],metric,metric)
    axes[0].legend(fontsize=9)
    return finish(fig,"08 · Classe A com duplo sinal definido antes do holdout","População fixa de 706 séries · apenas validação descritiva · sem recomendação de compra")


def uncertainty(d):
    fig,axes=plt.subplots(1,2,figsize=(13,5.5))
    names={"error_std":"Desvio histórico","rmse":"RMSE histórico","p90_absolute_error":"p90 histórico","p95_absolute_error":"p95 histórico"}
    q=d["uncertainty_quartiles"].loc[lambda x:x.model.eq("ets_ana")]
    for ax,target in zip(axes,["mae","rmse"]):
        for metric,part in q.groupby("historical_metric",sort=True):
            part=part.sort_values("historical_quartile")
            ax.plot(part.historical_quartile,part[target],marker="o",label=names[metric])
        ax.set(xticks=range(1,5),xticklabels=["Q1","Q2","Q3","Q4"],ylabel=target.upper()+" holdout",xlabel="Quartil da medida histórica")
    axes[0].legend(fontsize=9)
    return finish(fig,"09 · Incerteza anterior versus erro fora da amostra","Cortes calculados antes de abrir eval · erros agregados por quartil · associação também pode refletir escala")


def examples(d):
    examples=d["example_forecasts"]
    rules=sorted(examples.selection_rule.unique())
    fig,axes=plt.subplots(4,2,figsize=(14,14))
    for ax,rule in zip(axes.flat,rules):
        part=examples.loc[examples.selection_rule.eq(rule)]
        actual=part.loc[part.model.eq("ets_ana")].sort_values("dt")
        ax.plot(actual.dt,actual.actual,color="#263b46",marker="o",lw=1.3,label="Actual")
        for model,frame in part.groupby("model"):
            frame=frame.sort_values("dt")
            ax.plot(frame.dt,frame.forecast,color=COLORS[model],ls="--",label=NAMES[model])
        ax.set_title(f"{rule}\nloja {int(actual.store_id.iloc[0])} · produto {int(actual.product_id.iloc[0])}",fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.tick_params(labelsize=8)
    axes.flat[0].legend(fontsize=8)
    for ax in list(axes.flat)[len(rules):]:
        ax.set_visible(False)
    return finish(fig,"10 · Os mesmos sete exemplos da Fase 6","Seleção anterior ao holdout · nenhuma escolha baseada em resultado interessante de eval · escalas próprias por painel")


PLOTS=[global_metrics,lambda d:temporal(d,"wape",2),lambda d:temporal(d,"bias_pct",3),
    lambda d:segment(d,"abc","abc_class",["A","B","C"],4,"Erro por ABC"),
    lambda d:segment(d,"xyz","xyz_class",["X","Y","Z"],5,"Erro por XYZ"),
    persistent,risk,priority,uncertainty,examples]


def save_figure(fig,index,root=ROOT):
    folder=root/FOLDER/"figures"
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder/f"{index:02d}_holdout.png",dpi=135,bbox_inches="tight",facecolor="white")
