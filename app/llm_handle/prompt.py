
RETRIEVE_PROMPT = """
user asked {query} and similiar result filtered are {retrieved_content}
Using the results from a similarity search, your job is to evaluate and rank the information based on relevance to the user's query. 
Consider the context, accuracy, and timeliness of each result. Sort the information so that the most relevant and useful answers are presented first.
Provide the final answer in a clear, concise format that directly addresses the user's needs. 
If some results are not directly relevant, you may omit them from your response, but avoid stating irrelevance explicitly. 
If the search yields no useful information, simply return coudn't find anything would you elaborate you question
"""

SYSTEM_PROMPT = """
You are an intelligent AI assistant designed to provide accurate, relevant, and contextually appropriate answers. 
Your task is to craft well-structured and informative responses by analyzing the user's query and the provided search results.
Prioritize clarity and helpfulness in your answers, ensuring that the user receives the most relevant information based on their question.
"""

EXTRACT_RELEVANT_INFORMATION_PROMPT = """
### Schema:
{schema}

Query: {query}

### TASK:
Let's think step by step to extract the relevant information needed to build the query based on the schema.

1. Identify relevant nodes and their properties based on the schema.
2. Identify necessary relationships between the nodes.
3. Construct a path using relationships from the schema (connect from one node to the other to achive the query).
4. Include any specific IDs mentioned in the query.
5. Double check if the direction is reveresed. it is strict (source)-[predicate]->(target)

### STRICT RULES:
- Use only node types and relationships specified in the schema.
- Do not invent or reverse relationships.
- Ensure all nodes in relationships are included in the list.
- Only add property keys if mentioned in the query
- Never grab the property from the schema 
- Never infer an id from your knowledge

### RESPONSE FORMAT:
Provide your response in the following format:

**Relevant Nodes:**
- Node Type: `node_type1`
  - ID: `specific_id_or_empty_string`
  - Properties: 
    - key: value # ONLY if mentioned in the user Query

- Node Type: `node_type2`
  - ID: ``
  - Properties: 

- Node Type: `node_type3`
  - ID: ``
  - Properties:

**Relevant Relationships:** # ONLY if a connection of path is needed to acheive the query
For each relationship, specify the details as follows:

1. **Relationship 1:**
   - **Start Node:**
     - Type: `node_type1`
     - ID: `id_or_empty_string`
   - **Predicate:** `relationship_from_schema`
   - **End Node:**
     - Type: `node_type2`
     - ID: `id_or_empty_string`

2. **Relationship 2:**
   - **Start Node:**
     - Type: `node_type2`
     - ID: `id_or_empty_string`
   - **Predicate:** `another_relationship_from_schema`
   - **End Node:**
     - Type: `node_type3`
     - ID: `""`

(Continue for all relevant relationships)
"""