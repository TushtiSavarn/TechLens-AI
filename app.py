#libraries
import os
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_classic.chains.question_answering import load_qa_chain
from langchain_core.prompts import PromptTemplate 
from langchain_core.documents import Document
import time



#loading api key
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GROQ_API_KEY:
    st.error("Add GROQ_API_KEY to .env file")
    st.stop()
if not GEMINI_API_KEY:
    st.error("Add GEMINI_API_KEY to .env file")
    st.stop()

#custom configuration for streamlit page
st.set_page_config(
    page_title="TechLens AI",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Extract text from PDFs with source and page metadata
def get_pdf_text(uploaded_files):
    documents = []

    for file in uploaded_files:
        pdf_reader = PdfReader(file)

        for page_number, page in enumerate(pdf_reader.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": file.name,
                            "page": page_number
                        }
                    )
                )

    return documents

# Split documents while preserving metadata
def get_text_chunks(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    return splitter.split_documents(documents)

#create gemini embeddings
@st.cache_resource
def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    google_api_key=GEMINI_API_KEY
    )

# Create FAISS vector store
def get_vector_store(text_chunks):
    embeddings = get_embeddings()

    for attempt in range(2):
        try:
            vector_store = FAISS.from_documents(
                documents=text_chunks,
                embedding=embeddings
            )

            vector_store.save_local("faiss_index")
            return vector_store

        except Exception as error:
            if "RESOURCE_EXHAUSTED" in str(error) and attempt == 0:
                time.sleep(15)
            else:
                raise

# create q&a chain with memory 
def get_conversational_chain():
    prompt_template="""
    You are a helpful assistant that answers questions based on the context provided. If you don't know the answer, just say "I don't know". Do not try to make up an answer.Use the converstion history to understnad followup questions.Answer using the retrieved PDF context.If answer is not availble in the context ,say "Answer is not avaible in the context"Conversation History:{chat_history} PDF Context:{context}Current Question:{question}Answer:You are TechLens AI, an intelligent assistant for understanding PDF documents. Instructions: 1. Answer questions using only the information in the provided PDF context. 2. Do not invent facts or make unsupported assumptions. 3. If the answer is not available in the PDF context, say: "I couldn't find this information in the uploaded documents." 4. Use conversation history only to understand follow-up questions. 5. Keep answers clear, accurate, and concise. Conversation History: {chat_history} PDF Context: {context} Current Question: {question} Answer: """

    model=ChatGroq(
        model=os.getenv("GROQ_MODEL","openai/gpt-oss-120b"),
        temperature=0.3,api_key=GROQ_API_KEY
    )
    prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question", "chat_history"]
    )
    return load_qa_chain(
            model,
            chain_type="stuff",
            prompt=prompt
    )   
   

# Chat with PDFs using conversation memory and source tracking
def chat_with_pdf(question):
    embeddings = get_embeddings()

    db = FAISS.load_local(
        "faiss_index",
        embeddings,
        allow_dangerous_deserialization=True
    )

    docs = db.similarity_search(question, k=4)

    previous_messages = st.session_state.history[-5:]
    chat_history = ""

    for item in previous_messages:
        old_question, old_answer = item[:2]
        chat_history += f"User: {old_question}\n"
        chat_history += f"Assistant: {old_answer}\n"

    chain = get_conversational_chain()

    result = chain.invoke({
        "input_documents": docs,
        "question": question,
        "chat_history": chat_history
    })

    answer = result["output_text"]

    # Collect unique source references
    sources = []
    seen = set()

    for doc in docs:
        source = doc.metadata.get("source", "Unknown PDF")
        page = doc.metadata.get("page", "Unknown")

        reference = f"{source} — Page {page}"

        if reference not in seen:
            sources.append(reference)
            seen.add(reference)

    return answer, sources

# custom css for interface
def apply_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg: #0b0f14;
        --surface: #111923;
        --surface2: #151f2b;
        --border: #263442;
        --text: #e2eaf2;
        --muted: #8b9aaa;
        --cyan: #80ddeb;
        --lavender: #b8a9ed;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

.block-container {
    max-width: 1180px;
    padding-top: 4rem;
    padding-bottom: 3rem;
}

[data-testid="stHeader"] {
    background: rgba(11, 15, 20, 0.95);
}

[data-testid="stToolbar"] {
    right: 1rem;
}

    [data-testid="stSidebar"] {
        background: #0e141c;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.8rem;
    }

    h1, h2, h3 {
        color: var(--text) !important;
        letter-spacing: -0.035em;
    }

    p, label, .stMarkdown {
        color: #c0ccd8;
    }

    [data-testid="stChatMessage"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }

    [data-testid="stChatInput"] {
        border: 1px solid #344858;
        border-radius: 14px;
        background: var(--surface);
    }

    [data-testid="stChatInput"]:focus-within {
        border-color: var(--cyan);
        box-shadow: 0 0 0 1px rgba(128, 221, 235, 0.15);
    }

    .stButton > button {
        background: #172630;
        color: var(--cyan);
        border: 1px solid #36515e;
        border-radius: 9px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background: #1b303b;
        border-color: var(--cyan);
        color: #d8fbff;
        box-shadow: 0 0 12px rgba(128, 221, 235, 0.10);
    }

    [data-testid="stFileUploader"] {
        background: var(--surface);
        border: 1px dashed #344858;
        border-radius: 12px;
        padding: 10px;
    }

    [data-testid="stExpander"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
    }

    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        padding: 14px;
        border-radius: 12px;
    }

    .brand {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -1.5px;
        color: var(--text);
    }

    .brand span {
        color: var(--cyan);
    }

    .brand-subtitle {
        color: var(--muted);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 2px;
        margin-top: 3px;
    }

    .eyebrow {
        color: var(--cyan);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 1.5px;
    }

    .hero {
        background: linear-gradient(120deg, #121d29, #101720);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.7rem;
        margin: 1.2rem 0 1.5rem;
    }

    .hero-title {
        font-size: 1.8rem;
        font-weight: 650;
        letter-spacing: -1px;
        color: #e8f1f8;
        margin: 0.5rem 0;
    }

    .hero-description {
        color: var(--muted);
        font-size: 0.92rem;
        margin-bottom: 0;
    }

    .tech-label {
        color: #8296a9;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 1px;
    }

    hr {
        border-color: var(--border) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Streamlit interface
# Apply TechLens AI theme
apply_custom_css()

# Initialize conversation memory
if "history" not in st.session_state:
    st.session_state.history = []

# Sidebar
with st.sidebar:
    st.markdown("""
    <div class="brand">techlens<span>.</span></div>
    <div class="brand-subtitle">DOCUMENT INTELLIGENCE</div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("### Your workspace")
    st.caption("Upload documents to build your knowledge base.")

    uploaded_files = st.file_uploader(
        "Choose PDF documents",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} document(s) selected")

    if st.button("Process documents", use_container_width=True):
        if not uploaded_files:
            st.warning("Upload at least one PDF first.")
        else:
            try:
                with st.spinner("Reading and indexing documents..."):
                    raw_documents = get_pdf_text(uploaded_files)

                    if not raw_documents:
                        st.error("No readable text found in the PDFs.")
                    else:
                        chunks = get_text_chunks(raw_documents)
                        get_vector_store(chunks)

                        st.session_state["pdf_processed"] = True
                        st.session_state.history = []

                        st.success(
                            f"Indexed {len(chunks)} text chunks successfully."
                        )

            except Exception as error:
                st.error(f"Processing failed: {error}")

    st.divider()

    st.markdown("### Workspace status")

    if st.session_state.get("pdf_processed", False):
        st.success("Knowledge base ready")
    else:
        st.info("Waiting for documents")

    st.caption("POWERED BY")
    st.markdown(
        '<div class="tech-label">GEMINI · FAISS · GROQ · LANGCHAIN</div>',
        unsafe_allow_html=True
    )

    st.divider()

    if st.button("Clear chat history", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# Main workspace
st.markdown("""
<div class="eyebrow">01 / YOUR DOCUMENT WORKSPACE</div>
<div class="hero">
    <div class="eyebrow">◈ TECHLENS AI</div>
    <div class="hero-title">Think beyond the page.</div>
    <p class="hero-description">
        Explore your PDFs, ask questions and uncover information
        through context-aware AI.
    </p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**DOCUMENT INTELLIGENCE**")
    st.caption("Multi-PDF semantic search")

with col2:
    st.markdown("**CONVERSATIONAL AI**")
    st.caption("Context-aware answers with source references")

st.divider()

st.markdown("### Ask your documents")
st.caption("Ask a question about the PDFs you've processed.")

# Display conversation
for item in st.session_state.history:
    q, a = item[:2]
    sources = item[2] if len(item) > 2 else []

    with st.chat_message("user"):
        st.markdown(q)

    with st.chat_message("assistant"):
        st.markdown(a)

        if sources:
            with st.expander("View retrieved sources"):
                for source in sources:
                    st.markdown(f"- `{source}`")

# Chat input
question = st.chat_input("Ask something about your documents...")

if question:
    if not st.session_state.get("pdf_processed", False):
        st.warning("Please upload and process your PDFs first.")
    else:
        try:
            with st.spinner("Searching documents and generating an answer..."):
                answer, sources = chat_with_pdf(question)

            st.session_state.history.append(
                (question, answer, sources)
            )

            st.rerun()

        except Exception as error:
            st.error(f"Could not generate answer: {error}")