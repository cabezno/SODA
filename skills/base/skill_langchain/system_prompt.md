## Skill: LangChain

You are building an AI application with LangChain. Follow these conventions:

- Use `langchain` and `langchain-community` packages; for OpenAI use `langchain-openai`
- Use LangChain Expression Language (LCEL) with `|` pipe operator for chains: `chain = prompt | llm | parser`
- `ChatPromptTemplate.from_messages([("system", "..."), ("human", "{input}")])` for prompts
- For RAG: `RecursiveCharacterTextSplitter` → `Chroma` or `FAISS` vector store → `create_retrieval_chain`
- Use `ChatOpenAI` or `ChatAnthropic` as the LLM; pass `temperature=0` for deterministic tasks
- Memory/history: use `RunnableWithMessageHistory` with `ChatMessageHistory` for session-based memory
- Agents: `create_tool_calling_agent` + `AgentExecutor` for tool-using agents
- Always use `.ainvoke()` / `.astream()` for async contexts, not `.invoke()` / `.stream()`
- Streaming: `async for chunk in chain.astream({"input": ...}):` then `chunk.content`
- Vector stores persist to disk: `Chroma(persist_directory="./chroma_db", embedding_function=embeddings)`
