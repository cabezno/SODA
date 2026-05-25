def flatten_schema(schema: dict) -> dict:
    """
    Gemini API does not support '$defs' or '$ref'. 
    This helper inlines all definitions to create a self-contained flat schema.
    """
    if not schema:
        return schema

    defs = schema.get("$defs", schema.get("definitions", {}))
    
    def resolve_refs(obj: any):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"].split("/")[-1]
                if ref_path in defs:
                    # Replace ref with the actual definition content (recursively resolved)
                    return resolve_refs(defs[ref_path])
            return {k: resolve_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_refs(item) for item in obj]
        return obj

    # 1. Resolve all references in the main body
    new_schema = resolve_refs(schema)
    
    # 2. Remove the definitions block as it's now inlined
    if "$defs" in new_schema:
        del new_schema["$defs"]
    if "definitions" in new_schema:
        del new_schema["definitions"]
        
    return new_schema
