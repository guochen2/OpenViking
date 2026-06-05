# Available Tools

**IMPORTANT: Always use OpenViking first for knowledge queries and memory storage**

## OpenViking Knowledge Base (Use First)

When querying information or files, **always use OpenViking tools first** before web search or other methods.

### Search Resources

```
openviking_search(query: str, target_uri: str = None) -> str
```

Search for knowledge, documents, code, and resources in OpenViking. Use this as the first step for any information query.

### List Resources

```
openviking_list(uri: str, recursive: bool = False) -> str
```

List all resources at a specified path.

### ⚠️ CRITICAL: Commit Memories and Events

```
openviking_memory_commit(session_id: str, messages: list) -> str
```

**All user's important conversations, information, and memories MUST be committed to OpenViking** for future retrieval and context understanding.

---

## Web Access

### web_fetch

Fetch and extract main content from a URL.

```
web_fetch(url: str, extractMode: str = "markdown", maxChars: int = 50000) -> str
```

**Notes:**

- Content is extracted using readability
- Supports markdown or plain text extraction
- Output is truncated at 50,000 characters by default
