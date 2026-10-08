"""Executa a apresentação da Fase 3 na .venv, sem recálculos analíticos no notebook."""

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
    titles=[
        ("ABC por contribuição", "A/B/C é definido por produto, pelo acumulado antes do item. O item que cruza 80%/95% completa a classe."),
        ("Redundância das métricas", "Correlação não prova equivalência. A escolha mínima separa variação entre semanas da estabilidade da forma por weekday."),
        ("Regras XYZ", "Linhas mostram limites calculados em train. Z tem precedência, X exige ambos os critérios favoráveis e Y reúne os demais. Quatro indefinidos têm fallback explícito."),
        ("Diferenças entre classes", "A separação nas métricas da regra é esperada por construção. Lag 7 é evidência complementar e não confirma uma ordem de previsibilidade."),
        ("Tamanhos e sensibilidade", "Quatro regras transparentes foram comparadas. A escolha não força quantidades iguais nem usa erro de forecast."),
        ("Exposição à ruptura", "Exposição é frequência relativa, separada de XYZ. LOW não significa disponibilidade adequada durante todo o dia."),
        ("ABC × XYZ", "Classes de produto são propagadas às séries. Contagens de produtos nas células não são aditivas; séries e vendas são."),
        ("Disponibilidade dentro dos perfis", "A flag marca alta exposição à possível censura. Ela não mede demanda perdida nem substitui as demais dimensões."),
        ("Exemplos por regras", "Filtros e desempates ficam no pipeline. Os exemplos próximos da mediana usam apenas distância no CV semanal, sem score composto."),
    ]
    cells=[nbformat.v4.new_markdown_cell(
        "# Fase 3 — Segmentação e perfil operacional\n\n"
        "**Apenas train, ao corte de 25/06/2024. Eval congelado.**\n\n"
        "ABC do produto + XYZ da série + exposição/possível censura permanecem separados. "
        "Não há forecasting ou política de reposição. As nove figuras consomem outputs de "
        "`python scripts/build_segmentation.py`. Regras e tabelas completas em `docs/segmentation_report.md`.\n\n"
        "No backtesting futuro, recalcular ABC/XYZ/quantis em cada origem; este retrato final não pode ser reutilizado retrospectivamente."),
        nbformat.v4.new_code_cell(
        "%matplotlib inline\nfrom pathlib import Path\nimport sys\n"
        "root = Path.cwd()\nif not (root / 'src').is_dir():\n    root = root.parent\n"
        "sys.path.insert(0, str(root))\nimport matplotlib.pyplot as plt\nfrom IPython.display import display\n"
        "from src.reporting.segmentation_plots import load_outputs, PLOTS, save_figure\n"
        "data = load_outputs(root)\nassert data['summary']['source_split'] == 'train'\n"
        "print(f\"{data['summary']['n_products']} produtos; {data['summary']['n_series']:,} séries; corte {data['summary']['as_of']}\")")]
    for number,(title,comment) in enumerate(titles,1):
        cells.append(nbformat.v4.new_markdown_cell(f"## {number:02d}. {title}\n\n{comment}"))
        cells.append(nbformat.v4.new_code_cell(
            f"fig = PLOTS[{number-1}](data)\nsave_figure(fig, {number}, root)\ndisplay(fig)\nplt.close(fig)"))
    for index,cell in enumerate(cells):
        cell["id"]=f"phase3-cell-{index:02d}"
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
    path=ROOT / "notebooks/02_segmentation.ipynb"
    nbformat.write(notebook,path)
    print(f"Notebook executado: {path}; nove figuras em outputs/segmentation/figures.")


if __name__ == "__main__":
    main()
