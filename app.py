from flask import Flask, render_template, jsonify, request, session
from datetime import timedelta
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_openai import ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
import logging
from src.prompt import *
import os


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")  # replace in production
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False  # set True when enforcing HTTPS-only cookies
)
app.permanent_session_lifetime = timedelta(days=7)


load_dotenv()

REQUIRED_ENV = ["PINECONE_API_KEY", "OPENAI_API_KEY"]
missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
if missing:
    logging.warning(f"Missing environment variables: {missing}. The app will attempt to run but functionality may be limited.")

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Re-set to ensure downstream libraries see them
if PINECONE_API_KEY:
    os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY


embeddings = None
retriever = None
rag_chain = None
_pipeline_ready = False


def _build_pipeline():
    global embeddings, retriever, rag_chain, _pipeline_ready
    if _pipeline_ready:
        return
    try:
        embeddings = download_hugging_face_embeddings()
        index_name = "medical-chatbot"
        docsearch = PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embeddings
        )
        retriever_local = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        prompt_local = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )
        question_answer_chain_local = create_stuff_documents_chain(chatModel, prompt_local)
        rag_chain_local = create_retrieval_chain(retriever_local, question_answer_chain_local)
        retriever = retriever_local
        rag_chain = rag_chain_local
        _pipeline_ready = True
        logging.info("RAG pipeline built successfully.")
    except Exception as e:
        logging.warning(f"RAG pipeline build failed: {e}. Falling back to direct LLM.")

chatModel = ChatOpenAI(model="gpt-4o")



@app.route("/")
def index():
    session.permanent = True
    return render_template('chat.html')



@app.route("/get", methods=["GET", "POST"])
def chat():
    # Ensure pipeline is built lazily to avoid startup timeouts on Spaces
    if not _pipeline_ready:
        _build_pipeline()
    session.permanent = True
    msg = request.form["msg"].strip()
    history = session.get("history", [])
    # Special intent: report first prompt of current session
    normalized = msg.lower().strip().replace("?", "")
    if normalized in {"what was my first prompt", "what is my first prompt", "what was my first question", "what is my first question"}:
        first_user = next((content for role, content in history if role == "user"), None)
        if first_user:
            answer = f"Your first prompt was \"{first_user}\"."
        else:
            answer = "I don't see a previous prompt in this session yet."
        history.append(("user", msg))
        history.append(("assistant", answer))
        session["history"] = history
        return str(answer)
    # convert last 10 turns into LangChain message objects
    limited = history[-10:]
    lc_messages = []
    for role, content in limited:
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
    if rag_chain:
        response = rag_chain.invoke({"input": msg, "chat_history": lc_messages})
        answer = response.get("answer", "I don't know.")
    else:
        # Direct LLM fallback without retrieval context
        direct_prompt = system_prompt.replace('{context}', '(no retrieval)')
        # We do not embed history into prompt here; prompt template handles chat_history
        response = chatModel.invoke([
            HumanMessage(content=direct_prompt),
            *lc_messages,
            HumanMessage(content=msg)
        ])
        answer = getattr(response, 'content', "I don't know.")
    # update history
    history.append(("user", msg))
    history.append(("assistant", answer))
    session["history"] = history
    return str(answer)

@app.route("/reset", methods=["POST", "GET"])
def reset():
    session.pop("history", None)
    return jsonify({"status": "reset", "message": "Conversation history cleared."})

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "pinecone": bool(retriever),
        "openai_key": bool(OPENAI_API_KEY),
        "history_length": len(session.get("history", []))
    })



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
