"""Generate a small sample corpus (PDFs with text and figures) into contracts/sample_data/."""
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "contracts" / "sample_data"
OUT.mkdir(parents=True, exist_ok=True)
S = getSampleStyleSheet()


def diagram(path, labels, color):
    img = Image.new("RGB", (520, 260), "white")
    d = ImageDraw.Draw(img)
    x = 20
    for i, lab in enumerate(labels):
        d.rounded_rectangle([x, 90, x + 84, 170], 12, outline=color, width=4, fill=(245, 245, 250))
        d.text((x + 6, 124), lab, fill="black")
        if i < len(labels) - 1:
            d.line([x + 84, 130, x + 100, 130], fill=color, width=4)
        x += 100
    img.save(path)


def make(name, title, paras, fig_labels, fig_caption, color):
    png = OUT / f"_{name}.png"
    diagram(png, fig_labels, color)
    doc = SimpleDocTemplate(str(OUT / f"{name}.pdf"), pagesize=A4)
    story = [Paragraph(title, S["Title"])]
    for p in paras[:2]:
        story += [Paragraph(p, S["BodyText"]), Spacer(1, 10)]
    story += [RLImage(str(png), width=360, height=180), Paragraph(fig_caption, S["Italic"]), Spacer(1, 12)]
    for p in paras[2:]:
        story += [Paragraph(p, S["BodyText"]), Spacer(1, 10)]
    doc.build(story)
    png.unlink()


make("transformers_overview", "Transformer Models for Language Understanding", [
    "The Transformer architecture was introduced by Vaswani and colleagues in the paper Attention Is All You Need. It replaces recurrence with self-attention, which lets every token attend to every other token in the sequence.",
    "BERT is an encoder-only Transformer pretrained with masked language modelling on the BooksCorpus and English Wikipedia datasets. BERT improved the GLUE benchmark score over earlier recurrent models.",
    "GPT is a decoder-only Transformer trained with next-token prediction. GPT models scale well with data and parameters, and were evaluated on the LAMBADA and WikiText datasets.",
    "Training cost grows with sequence length because self-attention has quadratic complexity in the number of tokens.",
], ["Input", "Embedding", "Self-Attention", "Feed Forward", "Output"],
    "Figure 1: Architecture of a Transformer block with self-attention and feed forward layers.", (60, 90, 200))

make("retrieval_augmented_generation", "Retrieval-Augmented Generation Explained", [
    "Retrieval-Augmented Generation (RAG) combines a retriever with a language model. The retriever finds relevant passages in a document collection, and the language model writes an answer grounded in those passages.",
    "A typical RAG pipeline splits documents into chunks, embeds each chunk with an embedding model, and stores the vectors in a vector database. At query time the question is embedded and the nearest chunks are retrieved.",
    "GraphRAG extends RAG with a knowledge graph. Entities such as methods, datasets and authors become nodes, and relations become edges. GraphRAG answers multi-hop questions that plain RAG struggles with, for example which methods improved on BERT and which datasets they used.",
    "RAG reduces hallucination because the model can cite its sources. Faithfulness and contextual recall are common metrics for evaluating RAG systems.",
], ["Question", "Retriever", "Vector DB", "LLM", "Answer"],
    "Figure 1: The standard RAG pipeline from question to cited answer.", (200, 90, 60))

make("clip_and_multimodal", "CLIP and Multimodal Retrieval", [
    "CLIP, introduced by OpenAI, learns a shared embedding space for images and text using contrastive learning on 400 million image-text pairs.",
    "Because images and text share one vector space, CLIP supports text-to-image search: a query such as a block diagram of an encoder is embedded and compared directly with image embeddings.",
    "Multimodal RAG indexes figures with CLIP so that a user can retrieve charts and diagrams, not only text passages. Image-to-image search is also possible by embedding an uploaded picture.",
], ["Image", "Image Encoder", "Shared Space", "Text Encoder", "Text"],
    "Figure 1: CLIP aligns an image encoder and a text encoder in one shared embedding space.", (40, 150, 90))
print("sample PDFs written to", OUT)
