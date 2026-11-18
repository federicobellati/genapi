import os
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException

APP_DIR = Path(__file__).resolve().parent
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.248.224:8080/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-35b-a3b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))
MAX_DOCUMENT_BYTES = 1_000_000


def analyze(url: str) -> str:
    try:
        with requests.get(url, timeout=(10, 60), stream=True) as document:
            document.raise_for_status()
            content_type = document.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type and not (content_type.startswith("text/") or content_type in {"application/json", "application/xml", "application/xhtml+xml"} or content_type.endswith(("+json", "+xml"))):
                raise HTTPException(415, "L'URL deve restituire una pagina o un documento testuale (HTML, Markdown, JSON, XML, CSV o testo).")
            chunks, size = [], 0
            for chunk in document.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > MAX_DOCUMENT_BYTES:
                    raise HTTPException(413, "Il documento supera il limite di 1 MB: usare un URL con i soli metadati.")
                chunks.append(chunk)
            encoding = document.encoding if "charset=" in document.headers.get("Content-Type", "").lower() else "utf-8"
            content = b"".join(chunks).decode(encoding or "utf-8", errors="replace")
            final_url = document.url
    except requests.Timeout as exc:
        raise HTTPException(504, "Tempo scaduto durante il recupero del documento.") from exc
    except requests.RequestException as exc:
        raise HTTPException(502, "Impossibile recuperare il documento dall'URL indicato.") from exc
    if not content.strip():
        raise HTTPException(422, "Il documento recuperato è vuoto.")
    if content_type in {"text/html", "application/xhtml+xml"}:
        page = BeautifulSoup(content, "html.parser")
        embedded = [str(tag) for tag in page.find_all("meta")] + [tag.get_text() for tag in page.find_all("script") if tag.get("type", "").split(";")[0].lower() in {"application/ld+json", "application/json"}]
        for tag in page(["script", "style"]):
            tag.decompose()
        for link in page.find_all("a", href=True):
            link.append(f" [{urljoin(final_url, str(link['href']))}]")
        content = "\n".join(embedded + [page.get_text("\n", strip=True)])
        if not content.strip():
            raise HTTPException(422, "La pagina non contiene testo analizzabile; il codice JavaScript non viene eseguito.")
    prompt = (APP_DIR / "prompt.md").read_text(encoding="utf-8").replace("{url}", url)
    policy = (APP_DIR / "ISMAR_Data_Policy_v2.0_clean.md").read_text(encoding="utf-8")
    messages = [{"role": "system", "content": prompt + "\n\n<policy_doc>\n" + policy + "\n</policy_doc>"}, {"role": "user", "content": f"URL richiesto: {url}\nURL effettivo: {final_url}\n\n<dataset_doc>\n{content}\n</dataset_doc>"}]
    try:
        result = requests.post(LLM_BASE_URL + "/chat/completions", json={"model": LLM_MODEL, "messages": messages, "temperature": 0, "max_tokens": LLM_MAX_TOKENS, "stream": False, "chat_template_kwargs": {"enable_thinking": False}}, timeout=(10, LLM_TIMEOUT))
        if result.status_code == 400:
            error = result.json().get("error", {})
            if isinstance(error, dict) and error.get("type") == "exceed_context_size_error":
                raise HTTPException(413, f"Il documento con la policy richiede {error.get('n_prompt_tokens')} token; il modello accetta {error.get('n_ctx')}. Usare una pagina più piccola o aumentare il contesto sul server LLM.")
        result.raise_for_status()
        choice = result.json()["choices"][0]
        report = choice["message"]["content"]
    except requests.Timeout as exc:
        raise HTTPException(504, "Tempo scaduto durante l'analisi del modello LLM.") from exc
    except requests.RequestException as exc:
        raise HTTPException(502, "Il servizio LLM non è disponibile o ha rifiutato la richiesta; verificare anche la dimensione del documento rispetto al contesto del modello.") from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, "Il servizio LLM ha restituito una risposta non valida.") from exc
    if choice.get("finish_reason") == "length":
        raise HTTPException(502, "Il report è stato interrotto al limite di generazione: aumentare LLM_MAX_TOKENS.")
    if not isinstance(report, str) or not report.strip():
        raise HTTPException(502, "Il servizio LLM non ha restituito un report.")
    return report
