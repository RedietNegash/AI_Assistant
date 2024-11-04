# Handles graph-related operations like processing nodes, edges, generating responses ...
from collections import defaultdict
from app.services.annotation_service import query_knowledge_graph
from app.services.llm_models import GeminiModel,OpenAIModel
import re
import traceback
import json
import tiktoken
from flask import Flask

app = Flask(__name__)

class Graph_Summarizer:
    
    def __init__(self,llm) -> None:
        self.llm = llm
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def clean_and_format_response(self,desc):
        """Cleans the response from a model and formats it with multiple lines."""
        desc = desc.strip()
        desc = re.sub(r'\n\s*\n', '\n', desc)
        desc = re.sub(r'^\s*[\*\-]\s*', '', desc, flags=re.MULTILINE)
        lines = desc.split('\n')

        formatted_lines = []
        for line in lines:
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', line)
            for sentence in sentences:
                formatted_lines.append(sentence + '\n')
        formatted_desc = ' '.join(formatted_lines).strip()
        return formatted_desc


    def group_edges_by_source(self,edges):
        """Group edges by source_node."""
        grouped_edges = defaultdict(list)
        for edge in edges:
            source_node_id = edge["source_node"].split(' ')[-1]  # Extract ID
            grouped_edges[source_node_id].append(edge)
        return grouped_edges

    def generate_node_description(self,node):
        """Generate a description for a node with available attributes."""
        desc_parts = []

        for key, value in node.items():
            # Attempt to parse JSON-like strings into lists
            if isinstance(value, str):
                try:
                    parsed_value = json.loads(value)
                    if isinstance(parsed_value, list):
                        # Limit to top 3 items
                        top_items = parsed_value[:3]
                        if top_items:
                            desc_parts.append(f"{key.capitalize()}: {', '.join(top_items)}")
                        continue  # Move to the next attribute after processing
                except json.JSONDecodeError:
                    pass  # If not a JSON string, treat it as a regular string

            # For non-list attributes, simply add them to the description
            desc_parts.append(f"{key.capitalize()}: {value}")
        return " | ".join(desc_parts)


    def generate_grouped_descriptions(self,edges, nodes,batch_size=50):
        grouped_edges = self.group_edges_by_source(edges)
        # print (grouped_edges)
        descriptions = []

        # Process each source node and its related target nodes
        for source_node_id, related_edges in grouped_edges.items():
            source_node = nodes.get(source_node_id, {})
            source_desc = self.generate_node_description(source_node)

            # Collect descriptions for all target nodes linked to this source node
            target_descriptions = []
            for edge in related_edges:
                target_node_id = edge["target_node"].split(' ')[-1]
                target_node = nodes.get(target_node_id, {})
                target_desc = self.generate_node_description(target_node)

                # Add the relationship and target node description
                label = edge["label"]
                target_descriptions.append(f"{label} -> Target Node ({edge['target_node']}): {target_desc}")

            # Combine the source node description with all target node descriptions
            source_and_targets = (f"Source Node ({source_node_id}): {source_desc}\n" +
                                "\n".join(target_descriptions))
            descriptions.append(source_and_targets)
        return descriptions
    
    

    def nodes_description(self,nodes):
        nodes_descriptions = []
        # Process each source node and its related target nodes
        for source_node_id in nodes:
            source_node = nodes.get(source_node_id, {})
            source_desc = self.generate_node_description(source_node)
            nodes_descriptions.append(source_desc)
        return nodes_descriptions
    
    def num_tokens_from_string(self, encoding_name: str, max_tokens=2000):
        """Calculates the number of tokens in each description and groups them into batches under a token limit."""
        encoding = tiktoken.get_encoding(encoding_name)
        accumulated_tokens = 0
        grouped_descriptions = []
        self.current_batch = []  

        # Loop through each description
        for i, desc in enumerate(self.description, start=1):
            # Calculate the number of tokens in the current description
            desc_tokens = len(encoding.encode(desc))
            print(f"\n--- Processing Description {i} ---")
            print(f"Tokens in current description: {desc_tokens}")

            # Check if adding this description would exceed the max token limit
            if accumulated_tokens + desc_tokens <= max_tokens:
                # If within limit, add description to the current batch
                self.current_batch.append(desc)
                accumulated_tokens += desc_tokens
                print(f"Current Batch (Tokens: {accumulated_tokens}): {self.current_batch}")
            else:
                # If limit is exceeded, save the current batch
                grouped_descriptions.append(self.current_batch)
                print("\n** Batch Reached Max Token Limit **")
                print("Adding current batch to grouped descriptions:")
                print(self.current_batch)
                print("-------------------------------------------------------------")

                # Start a new batch with the current description
                self.current_batch = [desc]
                accumulated_tokens = desc_tokens  # Reset accumulated tokens for the new batch
                print(f"New Batch initialized with first description: {self.current_batch}")
                print(f"Accumulated tokens reset to: {accumulated_tokens}")

        # Add any remaining descriptions in the current batch
        if self.current_batch:
            grouped_descriptions.append(self.current_batch)
            print("\n** Final Batch **")
            print("Adding final batch to grouped descriptions:")
            print(self.current_batch)
            print("-------------------------------------------------------------")

        return grouped_descriptions


    def graph_description(self, graph):
        nodes = {node['data']['id']: node['data'] for node in graph['nodes']}
        
        if len(graph['edges']) > 0:
            edges = [{'source_node': edge['data']['source_node'],
                    'target_node': edge['data']['target_node'],
                    'label': edge['data']['label']} for edge in graph['edges']]
            self.description = self.generate_grouped_descriptions(edges, nodes, batch_size=10)
            print('self.description generated')
            # for index, description in enumerate(self.description):
            #     print(f"Index {index}:\n{description}\n{'-' * 40}")
            
            # Split descriptions by token limit
            batched_descriptions = self.num_tokens_from_string("cl100k_base")
            # print('total batched descritions',batched_descriptions)
            return batched_descriptions
        
        else:
            self.description = self.nodes_description(nodes)
            # print("Node descriptions:", self.description)
            return self.description

    def open_ai_summarizer(self, graph,user_query=None,query_json_format = None):
        try:
            self.graph_description(graph)
            print('current batch in the summerizer', self.current_batch)
            if user_query and query_json_format:
                prompt = (
                        f"You are an expert biology assistant on summarizing graph data.\n\n"
                        f"User Query: {user_query}\n\n"
                        f"Given the following data visualization:\n{self.current_batch }\n\n"
                        f"Your task is to analyze the graph and summarize the most important trends, patterns, and relationships.\n"
                        f"Instructions:\n"
                        f"- Begin by restating the user's query from {query_json_format} to show its relevance to the graph.\n"
                        f"- Focus on identifying key trends, relationships, or anomalies directly related to the user's question.\n"
                        f"- Highlight specific comparisons (if applicable) or variables shown in the graph.\n"
                        f"- Use bullet points or numbered lists to break down core details when necessary.\n"
                        f"- Format the response in a clear, concise, and easy-to-read manner.\n\n"
                        f"Please provide a summary based solely on the information shown in the graph."
                    )
            else:
                prompt = (
                        f"You are an expert biology assistant on summarizing graph data.\n\n"
                        f"Given the following graph data:\n{self.current_batch}\n\n"
                        f"Your task is to analyze and summarize the most important trends, patterns, and relationships.\n"
                        f"Instructions:\n"
                        f"- Identify key trends, relationships.\n"
                        f"- Use bullet points or numbered lists to break down core details when necessary.\n"
                        f"- Format the response clearly and concisely.\n\n"
                        f"Count and list important metrics"
                        F"Identify any central nodes or relationships and highlight any important patterns."
                        f"Also, mention key relationships between nodes and any interesting structures (such as chains or hubs)."
                        f"Please provide a summary based solely on the graph information."
                        f"Start with: 'The graph shows:'"
                    )


            response = self.llm.generate(prompt)
            # cleaned_desc = self.clean_and_format_response(response)
            return response
        except:
            traceback.print_exc()
    
    def explain_node(self, node_label, node_id):
        from app import schema_handler

        # Get relationships for the specified node
        node_relationships = schema_handler.get_relations_for_node(node_label)
        request_payloads = self.create_request_payloads(node_relationships, node_label, node_id)

        node_connections = self.fetch_knowledge_graph_data(request_payloads)
        explanation_prompt = self.construct_explanation_prompt(node_label, node_id, node_connections)

        response = self.llm.generate(explanation_prompt)
        # print(response)
        return response

    def create_request_payloads(self, node_relationships, node_label, node_id):
        """Constructs request payloads based on node relationships."""
        request_payloads = []
        for relationship in node_relationships:
            source_labels = self.ensure_list(relationship['source'])
            target_labels = self.ensure_list(relationship['target'])
            predicate = relationship['label']

            for source in source_labels:
                for target in target_labels:
                    if node_label == source:
                        request_payloads.append(self.format_request_payload(source, node_id, target, "", predicate))
                    elif node_label == target:
                        request_payloads.append(self.format_request_payload(source, "", target, node_id, predicate))
        return request_payloads

    def ensure_list(self, item):
        """Ensures the item is a list."""
        return [item] if isinstance(item, str) else item

    def format_request_payload(self, source_label, source_id, target_label, target_id, relation_type):
        """Fills the request template with the provided values."""
        request_template = """
        { 
            "nodes": [
                {
                    "node_id": "n1",
                    "id": "{{source_id}}",
                    "type": "{{source_lbl}}",
                    "properties": {}  
                },
                {
                    "node_id": "n2",
                    "id": "{{target_id}}",
                    "type": "{{target_lbl}}",
                    "properties": {}
                }
            ],
            "predicates": [
                {
                    "type": "{{relation}}",
                    "source": "n1",
                    "target": "n2"
                }
            ]
        }
        """
        return json.loads(
            request_template.replace("{{source_id}}", source_id)
                            .replace("{{source_lbl}}", source_label)
                            .replace("{{target_id}}", target_id)
                            .replace("{{target_lbl}}", target_label)
                            .replace("{{relation}}", relation_type)
        )

    def fetch_knowledge_graph_data(self, request_payloads):
        """Queries the knowledge graph and collects node connections."""

        config = current_app.config
        visited_node_ids = set()
        node_connections = {"nodes": [], "edges": []}

        for payload in request_payloads:
            kg_response = query_knowledge_graph(config['annotation_service_url'], payload)
            if kg_response['status_code'] == 200:
                self.process_kg_response(kg_response, visited_node_ids, node_connections)

        return node_connections

    def process_kg_response(self, kg_response, visited_node_ids, node_connections):
        """Processes the knowledge graph response to update node connections."""
        for node in kg_response['response']['nodes']:
            node_id = node['data']['id']
            if node_id not in visited_node_ids:
                visited_node_ids.add(node_id)
                node_connections['nodes'].append(node['data'])
        node_connections['edges'].extend(rel['data'] for rel in kg_response['response']['edges'])

    def construct_explanation_prompt(self, node_label, node_id, node_connections):
        """Creates a prompt for the LLM based on the node and its connections."""
        return (
        f"You are an expert bioinformatician. Please provide a structured explanation for the node '{node_label}' (ID: {node_id}).\n"
        f"This node has the following neighboring connections:\n{json.dumps(node_connections, indent=2)}\n"
        "In your response, please:\n"
        "- Include the properties of the node.\n"
        "- Summarize the key features and relationships.\n"
        "- Use bullet points for lists and clear sections for different aspects.\n"
        "Explain as clearly and concisely as possible, highlighting any significant patterns or insights."
    )

