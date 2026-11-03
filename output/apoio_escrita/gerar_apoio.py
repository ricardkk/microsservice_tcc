"""Deriva tabelas e figuras dos arquivos existentes, sem alterar a coleta.

Requer Python 3 com Matplotlib. Execute a partir da raiz do repositório:
    python3 output/apoio_escrita/gerar_apoio.py
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ENVS = ("non_centralized", "centralized")
ENV_NAMES = {"non_centralized": "Sem centralização", "centralized": "Centralizado"}
CASES = tuple(f"E{i:02d}" for i in range(1, 6))
SERVICES = ("gateway", "order-service", "user-service", "product-service")


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_runs():
    runs = {}
    for env in ENVS:
        paths = sorted((ROOT / "coleta" / "rodada-01" / env).glob("experiments/E*/*/metadata.json"))
        if len(paths) != 5:
            raise ValueError(f"Esperadas cinco execuções na rodada de {env}; encontradas {len(paths)}")
        for path in paths:
            meta = json.loads(path.read_text())
            events = []
            for log in sorted((path.parent / "logs").glob("*.log")):
                for line in log.read_text().splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("traceId") == meta["traceId"]:
                        events.append(event)
            runs[(env, meta["scenario"])] = (path, meta, events)
    return runs


def selected_timeline(events):
    def one(service, message):
        matches = [e for e in events if e["service"] == service and e["message"] == message]
        if len(matches) != 1:
            raise ValueError(f"Evento não é único: {service}, {message}")
        return matches[0]

    origin = instant(one("gateway", "Request started")["timestamp"])
    selected = {
        "gateway_start": one("gateway", "Request started"),
        "gateway_end": one("gateway", "Request completed"),
        "product_start": one("product-service", "Request started"),
        "product_end": one("product-service", "Request completed"),
        "order_timeout": one("order-service", "Timeout calling product-service"),
    }
    offsets = {key: (instant(e["timestamp"]) - origin).total_seconds() for key, e in selected.items()}
    if selected["gateway_end"]["status"] != 504 or selected["product_end"]["status"] != 200:
        raise ValueError("Status de E03 diferente da interpretação da figura")
    if not offsets["order_timeout"] < offsets["product_end"]:
        raise ValueError("A conclusão do Product não ocorreu após o timeout")
    return selected, offsets


def make_figure(runs):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"})
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 6.8), sharex=True)
    fig.suptitle("E03 — timeout no chamador e conclusão tardia da dependência", fontsize=13, y=0.98)
    manifest = []
    for ax, env in zip(axes, ENVS):
        path, meta, events = runs[(env, "E03")]
        selected, seconds = selected_timeline(events)
        ax.set_title(ENV_NAMES[env], loc="left", fontsize=11, pad=8)
        for service, y, start, end, color in [
            ("Gateway", 3, "gateway_start", "gateway_end", "#0072B2"),
            ("Product", 1, "product_start", "product_end", "#D55E00"),
        ]:
            ax.plot([seconds[start], seconds[end]], [y, y], color=color, lw=7, solid_capstyle="round")
            ax.scatter([seconds[start], seconds[end]], [y, y], color=color, s=28, zorder=4)
            status = selected[end]["status"]
            label = f"HTTP {status} · {seconds[end]:.3f} s".replace(".", ",")
            ax.annotate(label, (seconds[end], y), xytext=(0, 11), textcoords="offset points", ha="center", fontsize=9)
        ax.scatter([seconds["order_timeout"]], [2], marker="D", s=52, color="#7B3294", zorder=4)
        label = f"Timeout HTTP 504 · {seconds['order_timeout']:.3f} s".replace(".", ",")
        ax.annotate(label, (seconds["order_timeout"], 2), xytext=(0, 11), textcoords="offset points", ha="center", fontsize=9)
        ax.set_yticks([1, 2, 3], ["Product", "Order", "Gateway"])
        ax.set_ylim(0.55, 3.6)
        ax.set_xlim(-0.1, 5.9)
        ax.set_xticks(range(6))
        ax.grid(axis="x", color="#D9D9D9", linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#888888")
        ax.tick_params(axis="y", length=0)
        manifest.append({
            "environment": env,
            "metadata": str(path.relative_to(ROOT)),
            "traceId": meta["traceId"],
            "origin": selected["gateway_start"]["timestamp"],
            "events": {key: {"timestamp": value["timestamp"], "relative_seconds": seconds[key],
                               "status": value.get("status"), "service": value["service"],
                               "message": value["message"]} for key, value in selected.items()},
        })
    axes[-1].set_xlabel("Tempo desde o início da requisição no gateway de cada execução (s)", labelpad=8)
    fig.text(0.12, 0.09, "Traços: intervalos entre Request started e Request completed. Losango: registro de timeout no Order.", fontsize=8.5)
    fig.text(0.12, 0.055, "Fonte: elaboração própria com logs da rodada de 14/10/2026. Uma execução por ambiente.", fontsize=8.5)
    fig.text(0.12, 0.025, "Os tempos descrevem eventos da aplicação; não medem tempo de investigação ou ganho de diagnóstico.", fontsize=8.5)
    fig.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.2, hspace=0.58)
    fig.savefig(OUT / "linha_tempo_E03.png", dpi=300, facecolor="white")
    fig.savefig(OUT / "linha_tempo_E03.svg", facecolor="white")
    plt.close(fig)
    (OUT / "origem_linha_tempo_E03.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def make_event_distribution(runs):
    """Uma barra por caso: contagens por execução, iguais nos dois ambientes."""
    counts = {}
    manifest = []
    for case in CASES:
        environment_counts = []
        for env in ENVS:
            path, meta, events = runs[(env, case)]
            counter = Counter(event["service"] for event in events)
            if set(counter) - set(SERVICES):
                raise ValueError(f"Serviço não representado na figura: {env}, {case}")
            values = [counter[service] for service in SERVICES]
            environment_counts.append(values)
            manifest.append({
                "environment": env,
                "case": case,
                "metadata": str(path.relative_to(ROOT)),
                "traceId": meta["traceId"],
                "event_counts": dict(zip(SERVICES, values)),
                "total": sum(values),
            })
        if environment_counts[0] != environment_counts[1]:
            raise ValueError(f"Contagens diferentes entre ambientes em {case}; revisar a representação")
        counts[case] = environment_counts[0]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(9.5, 6.4))
    fig.suptitle("Distribuição dos eventos por serviço e caso experimental", fontsize=13, y=0.97)
    fig.text(0.5, 0.915, "Contagens por execução, coincidentes nos dois ambientes", ha="center", fontsize=10)
    positions = list(range(len(CASES)))
    bottom = [0] * len(CASES)
    colors = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")
    labels = ("Gateway", "Order", "User", "Product")
    text_colors = ("white", "#222222", "#111111", "#111111")
    for index, (label, color, text_color) in enumerate(zip(labels, colors, text_colors)):
        values = [counts[case][index] for case in CASES]
        ax.bar(positions, values, width=0.58, bottom=bottom, color=color,
               edgecolor="white", linewidth=0.7, label=label)
        for x, value, base in zip(positions, values, bottom):
            if value:
                ax.text(x, base + value / 2, str(value), ha="center", va="center",
                        fontsize=10, color=text_color)
        bottom = [base + value for base, value in zip(bottom, values)]
    for x, total in zip(positions, bottom):
        ax.text(x, total + 0.45, str(total), ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(positions, CASES)
    ax.set_xlabel("Caso experimental", labelpad=9)
    ax.set_ylabel("Eventos associados ao traceId")
    ax.set_ylim(0, max(bottom) + 3)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#888888")
    ax.tick_params(axis="y", length=0)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.015), frameon=False)
    fig.text(0.11, 0.105, "Cada barra representa um caso por ambiente; os dois ambientes não foram somados.", fontsize=8.5)
    fig.text(0.11, 0.065, "Fonte: elaboração própria com logs de 14/10/2026. Uma execução por caso em cada ambiente.", fontsize=8.5)
    fig.text(0.11, 0.025, "Valores representam eventos de log, não quantidades de erros ou acertos de diagnóstico.", fontsize=8.5)
    fig.subplots_adjust(left=0.11, right=0.97, top=0.80, bottom=0.23)
    fig.savefig(OUT / "eventos_por_servico.png", dpi=300, facecolor="white")
    fig.savefig(OUT / "eventos_por_servico.svg", facecolor="white")
    plt.close(fig)
    (OUT / "origem_eventos_por_servico.json").write_text(json.dumps({
        "selection": "Eventos cujo traceId corresponde ao metadata.json de cada execução",
        "representation": "Uma barra por caso, com contagens por execução iguais nos dois ambientes; sem soma entre ambientes",
        "runs": manifest,
    }, ensure_ascii=False, indent=2) + "\n")


def make_tables(runs):
    lines = [
        "# Tabelas derivadas da rodada de 14 de outubro de 2026", "",
        "Dados lidos dos metadados e dos eventos com o traceId de cada execução. Os arquivos originais não foram alterados.", "",
        "## Respostas observadas", "",
        "| Caso | Sem centralização | Centralizado | Ambos coincidem com o esperado? |",
        "|---|---|---|---|",
    ]
    for case in [f"E{i:02d}" for i in range(1, 6)]:
        metas = [runs[(env, case)][1] for env in ENVS]
        vals = [f"{m['observedResponse']['status']} / {m['observedResponse']['code']}" for m in metas]
        matches = all(m["expectedResponse"] == m["observedResponse"] for m in metas)
        lines.append(f"| {case} | {vals[0]} | {vals[1]} | {'Sim' if matches else 'Não'} |")
    lines += ["", "A conformidade HTTP é um resultado técnico; não representa acerto de diagnóstico de um investigador.", "",
              "## Eventos por requisição experimental", "",
              "| Caso | Eventos sem centralização | Eventos centralizados nos arquivos de origem | Eventos de origem verificados no Loki |",
              "|---|---:|---:|---:|"]
    totals = [0, 0, 0]
    for case in [f"E{i:02d}" for i in range(1, 6)]:
        a = len(runs[(ENVS[0], case)][2])
        b = len(runs[(ENVS[1], case)][2])
        o = runs[(ENVS[1], case)][1]["observability"]
        if not o["success"] or o["sourceEventsVerified"] != b:
            raise ValueError(f"Verificação Loki inconsistente em {case}")
        c = o["sourceEventsVerified"]
        lines.append(f"| {case} | {a} | {b} | {c} |")
        totals = [x + y for x, y in zip(totals, [a, b, c])]
    lines += [f"| Total | {totals[0]} | {totals[1]} | {totals[2]} |", "",
              "A última coluna descreve a verificação histórica registrada nos metadados; não é uma nova consulta ao Loki.",
              "As contagens não demonstram melhoria de diagnóstico, ausência geral de perdas ou entrega exatamente uma vez.", "",
              "## Eventos por serviço no ambiente centralizado", "",
              "| Caso | Gateway | Order | User | Product |", "|---|---:|---:|---:|---:|"]
    for case in [f"E{i:02d}" for i in range(1, 6)]:
        counts = Counter(e["service"] for e in runs[(ENVS[1], case)][2])
        values = [counts[s] for s in ["gateway", "order-service", "user-service", "product-service"]]
        lines.append(f"| {case} | " + " | ".join(map(str, values)) + " |")
    lines += ["", "As contagens por serviço coincidiram nos dois ambientes nesta rodada.",
              "Em E01, User e Product não foram chamados. Em E05, Product estava parado. Zeros não significam, por si só, perda na coleta.", "",
              "## Fontes e interpretação das figuras", "",
              "Figura 1: Sequência temporal do caso E03 nos dois ambientes (linha_tempo_E03.png e .svg).", "",
              "Fonte: elaboração própria com dados experimentais de 14/10/2026.", "",
              "O gateway retorna 504 aproximadamente dois segundos após receber a requisição. O Product conclui com 200 aproximadamente cinco segundos após o início. O mesmo padrão aparece nos dois ambientes.",
              "A origem e os instantes exatos estão em origem_linha_tempo_E03.json. A figura representa uma execução por ambiente; não apresenta médias ou intervalos de confiança.", "",
              "Figura 2: Distribuição dos eventos por serviço e caso experimental (eventos_por_servico.png e .svg).", "",
              "Uma barra por caso representa a contagem por execução, coincidente nos dois ambientes; os ambientes não foram somados. As contagens e suas fontes estão em origem_eventos_por_servico.json.",
              "Os valores descrevem eventos de log por serviço, não quantidades de erros ou acertos de diagnóstico.", "",
              "## Registros de origem", ""]
    for env in ENVS:
        for case in [f"E{i:02d}" for i in range(1, 6)]:
            path, meta, _ = runs[(env, case)]
            lines.append(f"- {env}, {case}: `{path.relative_to(ROOT)}`; trace `{meta['traceId']}`.")
    (OUT / "tabelas_resultados.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    all_runs = load_runs()
    make_figure(all_runs)
    make_event_distribution(all_runs)
    make_tables(all_runs)
    print("Tabelas e duas figuras derivadas de dez execuções; coleta preservada.")
