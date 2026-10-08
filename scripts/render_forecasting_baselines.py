"""Executa o notebook de dez figuras com o Python do projeto."""

import os
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager


ROOT=Path(__file__).resolve().parents[1]


def main():
    runtime=ROOT / ".tmp/jupyter_runtime"
    runtime.mkdir(parents=True,exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"]=str(runtime)
    os.environ["IPYTHONDIR"]=str(ROOT / ".ipython")
    os.environ["MPLCONFIGDIR"]=str(ROOT / ".matplotlib")
    topics=[
        ("Desenho dos folds","Origem é o primeiro dia previsto, antes de observar sua venda; cutoff é o dia anterior. Histórico crescente e testes sem sobreposição."),
        ("WAPE global","Métrica consolidada por somas. Seasonal Naive é referência pelo menor WAPE, com tradeoffs explicitados nas demais figuras."),
        ("MAE e RMSE","Erros na escala da venda observada normalizada. Não são unidades físicas, receita ou demanda latente."),
        ("Bias por série","Cada série recebe o mesmo peso na distribuição; os 28 dias são agregados antes do bias. Valores negativos representam subprevisão. Escala simétrica log para mostrar todas as caudas."),
        ("Performance XYZ","Classes e quantis recalculados a cada origem. A hipótese de menor erro em X tem apoio parcial, sem ordem universal nem ajuste posterior das regras."),
        ("Performance ABC","ABC global por produto, propagado para as séries. MAE e WAPE têm leituras distintas por causa da escala."),
        ("Melhoria relativa em ABC × XYZ","Positivo significa ganho do Seasonal Naive. C–Z é uma exceção; não aplicamos melhoria relativa ao bias assinado."),
        ("Disponibilidade e possível censura","Cortes descritivos, sem inferência causal. A flag piora ligeiramente em MAE/WAPE no Seasonal Naive, mas melhora RMSE e bias."),
        ("Estabilidade temporal","Desvio amostral entre quatro folds; não é intervalo de confiança. Z é mais estável em WAPE no Seasonal Naive, apesar do nível de erro maior."),
        ("Exemplos por regras","Seleção no último fold, com desempate por loja/produto. Melhor/pior/HIGH usam WAPE; subprevisão/flag usam bias mínimo; Naive supera SN usa maior diferença de WAPE. Extremos não representam a população. Denominadores acompanham os gráficos."),
    ]
    cells=[nbformat.v4.new_markdown_cell(
        "# Fase 4 — Forecasting baselines e backtesting temporal\n\n"
        "**Somente train. Eval congelado. Horizonte fixo de sete dias.**\n\n"
        "Quatro folds, 50.000 séries, dois baselines: 2.800.000 previsões. Este notebook consome outputs de "
        "`python scripts/run_baseline_backtest.py`. Lógica crítica em src; relatório completo em "
        "`docs/forecasting_baselines_report.md`. Não há modelos adicionais ou correção de censura.\n\n"
        "ABC, XYZ, exposição e flag são conhecidos em cada origem. O retrato full-train da Fase 3 não é usado nos folds."),
        nbformat.v4.new_code_cell(
        "%matplotlib inline\nfrom pathlib import Path\nimport sys\n"
        "root = Path.cwd()\nif not (root / 'src').is_dir():\n    root = root.parent\n"
        "sys.path.insert(0, str(root))\nimport matplotlib.pyplot as plt\nfrom IPython.display import display\n"
        "from src.reporting.forecast_plots import load_outputs, PLOTS, save_figure\n"
        "data = load_outputs(root)\nassert data['summary']['source_split'] == 'train'\n"
        "assert data['summary']['analysis_view'] == 'prospective'\n"
        "print(f\"{data['summary']['n_forecasts']:,} previsões; referência: {data['summary']['reference_baseline']}\")")]
    for number,(title,comment) in enumerate(topics,1):
        cells.extend([nbformat.v4.new_markdown_cell(f"## {number:02d}. {title}\n\n{comment}"),
            nbformat.v4.new_code_cell(f"fig = PLOTS[{number-1}](data)\nsave_figure(fig, {number}, root)\ndisplay(fig)\nplt.close(fig)")])
    cells.append(nbformat.v4.new_markdown_cell(
        "## Denominadores e conclusão\n\n"
        "263 séries×fold por modelo têm soma actual zero: WAPE e bias percentual ficam indefinidos, "
        "sem exclusão das métricas absolutas. No agregado dos quatro folds, nenhuma série tem soma zero. "
        "Denominadores e p05 de baixa escala constam no relatório e summary.json.\n\n"
        "Seasonal Naive reduz o WAPE global em 2,75%, mas perde em C–Z e na flag. A janela curta e os "
        "quatro folds limitam generalização; o bias negativo persiste. Manter ambos como referências "
        "para uma próxima fase autorizada, sem consultar eval."))
    for index,cell in enumerate(cells):
        cell["id"]=f"phase4-cell-{index:02d}"
    notebook=nbformat.v4.new_notebook(cells=cells,metadata={
        "kernelspec":{"display_name":"Python 3 (project .venv)","language":"python","name":"python3"}})
    manager=KernelManager(kernel_name="python3")
    manager.kernel_spec.argv=[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"]
    client=NotebookClient(notebook,km=manager,timeout=180,record_timing=False,resources={"metadata":{"path":str(ROOT)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    path=ROOT / "notebooks/03_forecasting_baselines.ipynb"
    nbformat.write(notebook,path)
    print(f"Notebook executado: {path}; dez figuras em outputs/forecasting_baselines/figures.")


if __name__ == "__main__":
    main()
