# Lumen: hybrid multimodal RAG research assistant

Upload PDFs, chat with an agent that answers with citations from your documents (text and figures),
and falls back to web search when your documents are not enough.

Keywords: RAG, GraphRAG, CLIP, LangGraph, MCP, DeepEval.

```
frontend/   web interface (vanilla HTML/CSS/JS, no build step)
backend/    FastAPI: documents, conversations, streaming chat (SQLite)
core/       AI core: ingestion, RAG, GraphRAG, CLIP, web search, LangGraph agent, citations, MCP server
contracts/  shared schemas, Mock Core, sample PDFs
eval/       DeepEval benchmark and dataset
tests/      pytest suite (runs fully offline)
GUIDE.md    step-by-step guide to finish and run everything  <-- start here
```

Quick start (offline demo, no API key):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
LLM_PROVIDER=fake ./run.sh          # then open http://localhost:8000
```

For real answers, follow GUIDE.md.

## Configuration testée : Groq

Le projet fonctionne avec n'importe quel serveur compatible OpenAI. Configuration testée avec Groq
(modèle `openai/gpt-oss-120b`) : dans `.env`, renseigner

    LLM_PROVIDER=openai
    LLM_MODEL=openai/gpt-oss-120b
    OPENAI_API_KEY=<votre clé Groq, ne jamais la committer>
    OPENAI_BASE_URL=https://api.groq.com/openai/v1
    GRAPH_EXTRACTION=false
    WEB_PROVIDER=none

Les noms de modèles disponibles changent selon le compte : vérifier la liste via
`GET https://api.groq.com/openai/v1/models` avec sa clé.

Chaque membre de l'équipe utilise sa propre clé. Le fichier `.env` est ignoré par Git.

## Documents en français

Pour des PDF en français, le modèle d'embeddings multilingue donne de meilleurs résultats :

    EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Si le modèle d'embeddings change, il faut réinitialiser les données (arrêter le serveur,
supprimer le dossier `data/`, relancer, recharger les PDF), car l'index et la base de
documents doivent rester cohérents.

## Corrections apportées

- `core/citations.py` : les marqueurs de citation `【1】` (crochets pleine largeur produits par
  certains modèles) sont normalisés en `[1]`, pour que les citations restent cliquables.
- `core/agent.py` : le prompt système interdit au modèle d'écrire des images ou liens markdown,
  car les figures sont affichées automatiquement par l'interface.

## Limites connues

- La recherche web est désactivée dans la configuration testée (`WEB_PROVIDER=none`).
- Le graphe de connaissances est désactivé par défaut (`GRAPH_EXTRACTION=false`) pour ménager
  les limites de requêtes du modèle.
- Les formules mathématiques des PDF sont extraites comme du texte et peuvent être déformées.
- Les images affichées ne sont pas filtrées par pertinence : une figure peu liée à la question
  peut apparaître en plus de la bonne.