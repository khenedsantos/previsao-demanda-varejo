"""Dez figuras da Fase 4, somente a partir dos outputs do backtest."""

import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from src.ingestion.source_manifest import ROOT
from src.reporting.demand_understanding_plots import finish, BLUE, GREEN, ORANGE


MODELS=["naive","seasonal_naive"]
LABELS={"naive":"Naive","seasonal_naive":"Seasonal Naive"}
COLORS={"naive":BLUE,"seasonal_naive":ORANGE}


def load_outputs(root=ROOT):
    folder=root / "data/outputs/forecasting_baselines"
    summary=json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    result={"summary":summary,"metrics":pd.DataFrame(summary["metrics"])}
    for name in ["relative_improvement","fold_stability","example_selection","example_forecasts","example_actuals"]:
        result[name]=pd.read_parquet(folder / f"{name}.parquet")
    result["series_bias"]=pd.read_parquet(root / summary["artifacts"]["metrics"]["path"],
        filters=[("level","=","series")],columns=["model","bias","bias_pct"])
    return result


def grouped(axis, frame, dimension, order, metric, title):
    positions=np.arange(len(order))
    for index,model in enumerate(MODELS):
        values=frame.loc[frame.model.eq(model)].set_index(dimension).reindex(order)[metric]
        axis.bar(positions+(index-.5)*.36,values,width=.34,label=LABELS[model],color=COLORS[model])
    axis.set(xticks=positions,xticklabels=[str(x) for x in order],title=title)
    if metric in {"wape","bias_pct"}:
        axis.yaxis.set_major_formatter(PercentFormatter(1))
    if metric in {"bias","bias_pct"}:
        axis.axhline(0,color="#6b7880",lw=.8)
    axis.legend(fontsize=8)


def folds(data):
    fig,axis=plt.subplots(figsize=(12,5))
    rows=data["summary"]["folds"]
    for row in rows:
        number=row["fold_id"]
        start=mdates.date2num(pd.Timestamp(row["history_start"]))
        origin=mdates.date2num(pd.Timestamp(row["forecast_origin"]))
        axis.broken_barh([(start,row["history_days"])],(number-.28,.56),facecolors=BLUE,label="Histórico" if number==1 else None)
        axis.broken_barh([(origin,7)],(number-.28,.56),facecolors=ORANGE,label="Teste: 7 dias" if number==1 else None)
        axis.text(start+2,number,f"{row['history_days']} dias",va="center",color="white",fontsize=10)
        axis.text(origin+3.5,number,f"{pd.Timestamp(row['test_start']):%d/%m}\na\n{pd.Timestamp(row['test_end']):%d/%m}",
                  ha="center",va="center",color="white",fontsize=8)
    axis.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.WE,interval=2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axis.set(yticks=[1,2,3,4],yticklabels=["Fold 1","Fold 2","Fold 3","Fold 4"],ylim=(4.6,.4),xlabel="2024 · datas dentro de train")
    axis.legend(loc="lower left",ncol=2)
    return finish(fig,"01 · Quatro origens com histórico crescente",
        "Origem = primeiro dia previsto, antes de observá-lo. Cada segmento é recalculado até o dia anterior; eval não participa.")


def global_wape(data):
    part=data["metrics"].loc[data["metrics"].level.eq("global")].set_index("model").reindex(MODELS)
    fig,axis=plt.subplots(figsize=(9,5))
    bars=axis.bar([LABELS[m] for m in MODELS],part.wape,color=[COLORS[m] for m in MODELS],width=.55)
    axis.bar_label(bars,labels=[f"{v:.2%}" for v in part.wape],padding=5)
    axis.set(ylim=(0,.53),ylabel="WAPE global consolidado")
    axis.yaxis.set_major_formatter(PercentFormatter(1))
    gain=(part.loc["naive","wape"]-part.loc["seasonal_naive","wape"])/part.loc["naive","wape"]
    return finish(fig,"02 · Seasonal Naive reduz o WAPE global",
        f"Melhoria relativa: {gain:.2%} · 1,4 milhão de previsões por modelo · soma dos erros absolutos / soma dos actuals.")


def absolute_errors(data):
    part=data["metrics"].loc[data["metrics"].level.eq("global")].set_index("model").reindex(MODELS)
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    for axis,metric in zip(axes,["mae","rmse"]):
        bars=axis.bar([LABELS[m] for m in MODELS],part[metric],color=[COLORS[m] for m in MODELS],width=.55)
        axis.bar_label(bars,labels=[f"{v:.4f}" for v in part[metric]],padding=4)
        axis.set(title=metric.upper(),ylabel="Venda observada normalizada",ylim=(0,part[metric].max()*1.2))
    return finish(fig,"03 · Também há ganho em MAE e RMSE",
        "RMSE dá mais peso aos erros grandes. Escala normalizada da fonte: não são unidades físicas, receita ou demanda latente.")


def bias_distribution(data):
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for axis,metric,title in zip(axes,["bias","bias_pct"],["Bias na escala da venda","Bias percentual"]):
        for model in MODELS:
            values=np.sort(data["series_bias"].loc[data["series_bias"].model.eq(model),metric].dropna())
            axis.plot(values,np.arange(1,len(values)+1)/len(values),label=LABELS[model],color=COLORS[model])
        axis.axvline(0,color="#647681",ls="--",lw=1)
        axis.set(xscale="symlog",xlabel=title+" · escala simétrica log",ylabel="Parcela acumulada das séries",ylim=(0,1))
        axis.set_xscale("symlog",linthresh=.03)
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        if metric=="bias_pct":
            axis.xaxis.set_major_formatter(PercentFormatter(1))
        axis.legend(loc="lower right",fontsize=9)
    return finish(fig,"04 · Subprevisão persiste na maioria das séries",
        "Bias = forecast − actual, agregado nos 28 dias por série. Distribuição completa; valores negativos indicam subprevisão.")


def xyz(data):
    part=data["metrics"].loc[data["metrics"].level.eq("xyz")]
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for axis,metric,title in zip(axes.flat,["wape","bias_pct","mae","rmse"],["WAPE","Bias percentual","MAE","RMSE"]):
        grouped(axis,part,"xyz_class",["X","Y","Z"],metric,title)
    return finish(fig,"05 · X tem menor WAPE; a ordem não vale para toda métrica",
        "Classes conhecidas em cada origem. Y tem MAE/RMSE menores que X; menor WAPE não garante menor variação entre folds (figura 09).")


def abc(data):
    part=data["metrics"].loc[data["metrics"].level.eq("abc")]
    fig,axes=plt.subplots(1,3,figsize=(13,5))
    for axis,metric,title in zip(axes,["wape","mae","bias_pct"],["WAPE","MAE","Bias percentual"]):
        grouped(axis,part,"abc_class",["A","B","C"],metric,title)
    return finish(fig,"06 · A tem maior erro absoluto, mas menor WAPE",
        "ABC por contribuição do produto, recalculado em cada origem e propagado às séries; não é classificação financeira.")


def improvements(data):
    frame=data["relative_improvement"]
    fig,axes=plt.subplots(1,2,figsize=(12,5.5))
    for axis,metric in zip(axes,["wape","rmse"]):
        matrix=frame.loc[frame.level.eq("abc_xyz")&frame.metric.eq(metric)].pivot(index="abc_class",columns="xyz_class",values="relative_improvement").reindex(index=list("ABC"),columns=list("XYZ"))
        axis.imshow(matrix,cmap="RdYlGn",vmin=-.12,vmax=.12,aspect="auto")
        axis.set(xticks=[0,1,2],xticklabels=list("XYZ"),yticks=[0,1,2],yticklabels=list("ABC"),title=f"Melhoria relativa · {metric.upper()}",xlabel="XYZ",ylabel="ABC")
        axis.grid(False)
        for i in range(3):
            for j in range(3):
                axis.text(j,i,f"{matrix.iloc[i,j]:+.2%}",ha="center",va="center",fontsize=13,color="#162d3a")
    fig=finish(fig,"07 · O ganho semanal é maior em B; C–Z é exceção",
        "(Naive − Seasonal Naive) / Naive · verde = melhora; vermelho = piora · métricas consolidadas, segmentos prospectivos.")
    for axis in axes:
        axis.grid(False)
    return fig


def availability(data):
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for index,(level,dimension,order,title) in enumerate([
        ("stockout_exposure","stockout_exposure",["LOW","MEDIUM","HIGH"],"Exposição"),
        ("censoring_risk_flag","censoring_risk_flag",[False,True],"Flag de possível censura")]):
        part=data["metrics"].loc[data["metrics"].level.eq(level)]
        for j,metric in enumerate(["wape","bias_pct"]):
            grouped(axes[index,j],part,dimension,order,metric,f"{title} · {'WAPE' if metric=='wape' else 'bias %'}")
    return finish(fig,"08 · A flag concentra maior WAPE e subprevisão",
        "HIGH tem menor WAPE, mas maior MAE/RMSE e bias negativo. Denominadores diferem; associação não demonstra causalidade.")


def stability(data):
    part=data["metrics"].loc[data["metrics"].level.eq("fold")]
    fig,axes=plt.subplots(1,3,figsize=(14,5))
    for axis,metric in zip(axes[:2],["wape","bias_pct"]):
        for model in MODELS:
            rows=part.loc[part.model.eq(model)].sort_values("fold_id")
            axis.plot(rows.fold_id,rows[metric],"o-",color=COLORS[model],label=LABELS[model])
        axis.set(xticks=[1,2,3,4],xlabel="Fold",title="WAPE" if metric=="wape" else "Bias percentual")
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.legend(fontsize=8)
    axes[1].axhline(0,color="#647681",lw=.8)
    group=data["fold_stability"].loc[data["fold_stability"].level.eq("xyz")]
    grouped(axes[2],group,"xyz_class",["X","Y","Z"],"wape_std","Desvio entre folds · WAPE")
    axes[2].yaxis.set_major_formatter(PercentFormatter(1))
    return finish(fig,"09 · Menor erro global não garante menor variabilidade",
        "Seasonal Naive vence em WAPE nos quatro folds; seu desvio global é ligeiramente maior. Em SN, Z é mais estável que X/Y.")


def examples(data):
    chosen=data["example_selection"]
    forecasts=data["example_forecasts"]
    actuals=data["example_actuals"]
    names=["Melhor SN em AX","Pior SN em AX","Maior subprevisão AZ","HIGH com maior WAPE","Flag com menor bias","Naive supera SN"]
    fig,axes=plt.subplots(3,2,figsize=(14,12))
    for axis,(_,row),title in zip(axes.flat,chosen.iterrows(),names):
        observed=actuals.loc[actuals.selection_rule.eq(row.selection_rule)]
        dates=pd.to_datetime(observed.dt)
        origin=pd.Timestamp(row.forecast_origin)
        axis.plot(dates,observed.sale_amount,color="#243b4a",lw=1.7,label="Actual")
        affected=observed.stock_hour6_22_cnt.gt(0)
        axis.scatter(dates[affected],observed.loc[affected,"sale_amount"],s=24,facecolors="none",edgecolors=GREEN,label="Dia com ruptura")
        for model in MODELS:
            p=forecasts.loc[forecasts.selection_rule.eq(row.selection_rule)&forecasts.model.eq(model)]
            axis.plot(pd.to_datetime(p.target_date),p.forecast,"o--",ms=3,color=COLORS[model],label=LABELS[model])
        axis.axvline(origin,color="#647681",ls=":")
        axis.axvspan(origin,origin+pd.Timedelta(days=6),color="#eef2f4",zorder=-1)
        axis.set_title(f"{title} · loja {int(row.store_id)} / produto {int(row.product_id)}\n"
                       f"D={row.actual_sum:.2f} · WAPE SN={row.wape:.1%} · bias SN={row.bias:.3f}",fontsize=10)
        axis.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        axis.set_ylabel("Venda normalizada")
        axis.legend(fontsize=7,loc="upper left",ncol=2)
    return finish(fig,"10 · Exemplos extremos, selecionados por regras e IDs",
        "Último fold · sombra = horizonte de 19–25/06 · 14 dias prévios para contexto · WAPE extremo pode refletir denominador muito pequeno.")


PLOTS=[folds,global_wape,absolute_errors,bias_distribution,xyz,abc,improvements,availability,stability,examples]


def save_figure(fig, number, root=ROOT):
    folder=root / "data/outputs/forecasting_baselines/figures"
    folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder / f"{number:02d}_forecasting_baselines.png",dpi=145,facecolor="white")
