# LangChain Best Practices

## Basic LCEL chain
```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(model="gpt-4o", temperature=0)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{input}"),
])
chain = prompt | llm | StrOutputParser()

result = await chain.ainvoke({"input": "Hello!"})
```

## RAG pipeline
```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# Index documents
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(documents)
vectorstore = Chroma.from_documents(chunks, OpenAIEmbeddings(), persist_directory="./db")

# Query
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
combine_chain = create_stuff_documents_chain(llm, qa_prompt)
rag_chain = create_retrieval_chain(retriever, combine_chain)
answer = await rag_chain.ainvoke({"input": question})
```

## Conversation memory
```python
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

store = {}  # session_id → ChatMessageHistory

def get_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

chain_with_history = RunnableWithMessageHistory(
    chain, get_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)
response = await chain_with_history.ainvoke(
    {"input": message},
    config={"configurable": {"session_id": session_id}},
)
```

## Streaming
```python
async for chunk in chain.astream({"input": user_message}):
    yield chunk  # each chunk is a string fragment
```
