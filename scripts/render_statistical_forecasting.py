"""Executa dez figuras da Fase 5 a partir dos outputs, sem qualquer ajuste ETS."""

import os
from pathlib import Path
import sys
from time import perf_counter

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from src.forecasting.statistical_backtesting import write_json
    from src.forecasting.backtesting import peak_working_set_bytes

    started=perf_counter()
    runtime=ROOT / ".tmp/jupyter_runtime"
    runtime.mkdir(parents=True,exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"]=str(runtime)
    os.environ["IPYTHONDIR"]=str(ROOT / ".ipython")
    os.environ["MPLCONFIGDIR"]=str(ROOT / ".matplotlib")
    topics=[
        ("Erros globais","Métricas consolidadas por somas; mesma cobertura e denominador. Fallback, se houver, integra o candidato solicitado."),
        ("Comparação por fold","Quatro janelas sem sobreposição. WAPE e bias são mostrados juntos para explicitar tradeoffs."),
        ("ABC","Contribuição do produto conhecida até cada corte. Escala muda a leitura de MAE e WAPE."),
        ("XYZ","Classes prospectivas preservadas da Fase 4; não foram redefinidas para favorecer ETS."),
        ("ABC × XYZ","Melhoria = (Seasonal Naive − ETS) / Seasonal Naive. Referência zero produz nulo. Não aplicar a bias assinado."),
        ("Exposição e flag","Associações com disponibilidade, sem efeito causal identificado ou estimativa de demanda perdida."),
        ("Distribuição de bias","Os 28 dias são agregados por série antes dos quantis. Cada série tem peso igual; bias negativo representa subprevisão."),
        ("Win rate e materialidade","Win rate pareado; tolerância atol=1e-12, rtol=1e-10. Em ABC/XYZ, agregam-se apenas os folds em que cada classe era conhecida; uma série pode aparecer em classes diferentes. As tabelas abaixo incluem os limiares descritivos solicitados."),
        ("Fallback e clipping","Fallback é uma decisão por ajuste. Clipping é projeção de forecast negativo em zero, preservando seu valor original; não é falha."),
        ("Exemplos reproduzíveis","Extremos do último fold, desempate por loja/produto. Ganho/piora por WAPE e variação do bias. Fallback, se existir, usa a origem mais recente disponível. Exemplos não representam a população nem selecionam modelos."),
    ]
    cells=[nbformat.v4.new_markdown_cell(
        "# Fase 5 — ETS A/N/A versus Seasonal Naive\n\n"
        "**Somente train; eval congelado. 50.000 séries × quatro folds × sete dias.**\n\n"
        "Candidato fixado antes dos resultados: sem tendência, sazonalidade aditiva semanal; SLSQP, "
        "maxiter=200, ftol=1e-6, use_brute=False, remove_bias=False.\n\n"
        "Este notebook consome os outputs de `scripts/run_statistical_forecast.py`; não ajusta modelos. "
        "A lógica está em src. Target = venda observada normalizada, não demanda latente. "
        "Relatório completo: `docs/statistical_forecasting_report.md`."),
        nbformat.v4.new_code_cell(
        "%matplotlib inline\nfrom pathlib import Path\nimport sys\n"
        "root = Path.cwd()\nif not (root / 'src').is_dir():\n    root = root.parent\n"
        "sys.path.insert(0, str(root))\nimport matplotlib.pyplot as plt\nimport pandas as pd\n"
        "from IPython.display import display\nfrom src.reporting.statistical_plots import load_outputs, PLOTS, save_figure\n"
        "data = load_outputs(root)\nassert data['summary']['source_split'] == 'train'\n"
        "assert data['summary']['analysis_view'] == 'prospective'\n"
        "display(pd.DataFrame(data['summary']['folds']))\n"
        "display(data['metrics'].loc[data['metrics'].level.eq('global'), "
        "['model','n_forecasts','actual_sum','mae','rmse','wape','bias','bias_pct']])")]
    for number,(title,comment) in enumerate(topics,1):
        source=f"fig = PLOTS[{number-1}](data)\nsave_figure(fig, {number}, root)\ndisplay(fig)\nplt.close(fig)"
        if number==8:
            source+="\ndisplay(data['win_rates'])\ndisplay(data['materiality'])"
        if number==9:
            source+="\ndisplay(data['fit_diagnostics'].loc[data['fit_diagnostics'].level.isin(['global','fold'])])"
        cells.extend([nbformat.v4.new_markdown_cell(f"## {number:02d}. {title}\n\n{comment}"),nbformat.v4.new_code_cell(source)])
    cells.extend([nbformat.v4.new_markdown_cell(
        "## Potencial híbrido e limites\n\n"
        "Análise predefinida antes dos resultados: usar ETS no segmento ABC×XYZ somente após pelo menos "
        "dois folds passados, todos com melhoria em WAPE, sem perda em RMSE e sem piora do bias absoluto "
        "consolidado. Os dois primeiros folds usam SN. A classe do fold corrente vem de seu snapshot prospectivo. "
        "Nenhum erro do próprio fold decide a escolha. Não é política operacional final.\n\n"
        "Quatro folds e 28 dias de avaliação não garantem generalização. Não há MAPE, tuning, correção de censura "
        "ou uso de eval. Métricas percentuais com D=0 ficam nulas; nenhum caso é removido dos erros absolutos. "
        "Reprodução inclui contratos, hashes e pequena amostra de ajustes, sem segunda execução populacional.\n\n"
        "**Classificação da evidência: A — ETS claramente superior neste backtest.** Ganho global de MAE/WAPE "
        "de 14,82% e RMSE de 13,32%, nos quatro folds e em todos os segmentos predefinidos. "
        "Bias global melhora de −3,27% para −2,17%, mas a distribuição por série se alarga; a magnitude do bias "
        "piora nos folds 1, 2 e 3. ETS vence MAE/WAPE em 88,406% das séries; 4,256% pioram pelo menos 10%. "
        "A regra híbrida conservadora melhora WAPE em apenas 2,15% sobre SN e fica atrás de ETS uniforme. "
        "Conclusão restrita ao backtest observado; não é adoção operacional nem garantia no holdout."),
        nbformat.v4.new_code_cell(
        "display(pd.DataFrame(data['summary']['hybrid_metrics']))\n"
        "display(pd.DataFrame(data['summary']['denominator_diagnostics']))\n"
        "from src.forecasting.backtesting import peak_working_set_bytes\n"
        "from src.forecasting.statistical_backtesting import write_json\n"
        "write_json(root / 'data/outputs/statistical_forecasting/notebook_kernel_performance.json', "
        "{'peak_working_set_bytes': peak_working_set_bytes(), 'scope': 'notebook kernel only'})")])
    for index,cell in enumerate(cells):
        cell["id"]=f"phase5-cell-{index:02d}"
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={"kernelspec":{
        "display_name":"Python 3 (project .venv)","language":"python","name":"python3"}})
    manager=KernelManager(kernel_name="python3")
    manager.kernel_spec.argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"]
    client=NotebookClient(notebook,km=manager,timeout=180,record_timing=False,resources={"metadata":{"path":str(ROOT)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    path=ROOT / "notebooks/04_statistical_forecasting.ipynb"
    nbformat.write(notebook,path)
    write_json(ROOT / "data/outputs/statistical_forecasting/notebook_performance.json",{
        "seconds":perf_counter()-started,"runner_peak_working_set_bytes":peak_working_set_bytes(),
        "notebook_bytes":path.stat().st_size,"scope":"rendering and writing executed notebook; no fits"})
    print("Notebook Fase 5 executado; dez figuras e tabelas, sem novos ajustes.")


if __name__=="__main__":
    main()
