import os
from pymongo import MongoClient
from flask import Blueprint, request, jsonify

import openai
import re
import json

mongo_client = MongoClient(os.environ["DB_CONNECTION_STRING"])

gen_config_bp = Blueprint("gen_config", __name__)

def run_sim(def_prompt, json_prompt, desc_prompt):
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    while True:
        print("Running sim to generate config")

        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": def_prompt},
                {"role": "user", "content": json_prompt},
                {"role": "user", "content": desc_prompt}
            ]
        )

        response_str = response.choices[0].message.content.replace("\n", "").replace("```json", "").replace("```", "")
        #print(response_str)

        json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
        if not json_match:
            continue
            
        try:
            parsed_json = json.loads(json_match.group(0))
            for variable in parsed_json:
                if parsed_json[variable] == None:
                    continue
        except json.JSONDecodeError:
            continue

        return response_str

@gen_config_bp.route("/gen_config", methods=["POST"])
def generate_config():
    request_json = request.get_json()

    desc = request_json["desc"]
    if not desc:
        return jsonify({"message": "desc not given"}), 400
    
    JSON_CONFIG_PROMPT = """
        This is the config file output template:
        {
            "num_runs": 999,
            "config": {
                "name": "Name Of Simulation",
                "agents": [
                 {
                    "name": "First AI Agents Name",
                    "description": "Description of the First AI Agent",
                    "prompt": "Prompt to be given to the First AI Agent, this should tell them who they are and what they want"
                 }
                ],
                "termination_condition": "The event that triggers the end of the simulation",
                "output_variables": [
                 {
                    "name": "First Output Variable Name",
                    "type": "First Output Variable Type (e.g. String, Number, etc)"
                 },
                 {
                    "name": "placeholder2",
                    "type": "Number"
                 }
                ]
            }
        }
        Please replace all values in the template and do not add any keys not already written into the template. You may add as many agents or output variables as needed.
        """
    
    DEFAULT_PROMPT = """
        You are an AI Assistent who converts a plain text description of a multi-agent AI simulation into a valid JSON config file.
        You should insert one agent into the config for each person or sentient entity in the description. All humans should be given a unique name such as "Teacher" or "Sarah", but not "Agent 3".
        You should also include as many output variables as needed to determine the result of the simulation.
        Output variables should be concrete and not vague, the name alone should describe the units, range or any other information such that all simulations will fill the variables with comparable data.
        If an output variable is a percentage that should be mentioned in the name explicitly. Do not write output variables in snake case, pascal case, etc.
        You should never have only 0 or 1 agents, or no output variables
    """

    prompt = "\n\nThis is your simulation description: " + desc + "\n\nDo not write anything except the JSON" 

    config_str = run_sim(DEFAULT_PROMPT, JSON_CONFIG_PROMPT, prompt)   

    return jsonify(json.loads(config_str))