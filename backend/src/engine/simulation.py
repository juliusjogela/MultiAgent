import re
import os
import json

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console

class SelectorGCSimulation:
    def __init__(self, config, max_messages=25, min_messages=5):
        self.model_client = OpenAIChatCompletionClient(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"])
        self.config = config
        self.min_messages = min_messages

        self.config_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")

        # inject InformationReturnAgent into config
        if not any(agent["name"] == "InformationReturnAgent" for agent in self.config["agents"]): # check if InformationReturnAgent is there already
            with open(os.path.join(self.config_directory, "InformationReturnAgent.json"), "r", encoding="utf-8") as file:
                information_return_agent = json.load(file)
                information_return_agent["prompt"] = information_return_agent["prompt"].format(
                    output_variables_str = (
                        '{\n' + ",\n".join([
                            f'"{v["name"]}": "{ "STRING" if v["type"] == "String" else "NUMBER" }"'
                            for v in self.config["output_variables"]
                        ]) + '\n}'
                    ),
                    termination_condition=self.config["termination_condition"]
                )
                self.config["agents"].append(information_return_agent)
    
        # initialize agents
        self.agents = [
            AssistantAgent(
                agent["name"],
                description=agent["description"],
                model_client=self.model_client,
                system_message=agent["prompt"]
            ) for agent in self.config["agents"]
        ]

        # initialize group chat
        with open(os.path.join(self.config_directory, "selector_prompt.txt"), "r", encoding="utf-8") as file:
            selector_prompt = file.read()

        self.gc = SelectorGroupChat(
            self.agents,
            model_client=self.model_client,
            selector_prompt=selector_prompt,
            termination_condition=(
                TextMentionTermination("TERMINATE") | MaxMessageTermination(max_messages=max_messages)
            )
        )

    def _process_result(self, simulation_result):
        if len(simulation_result.messages) < self.min_messages:
            return None

        messages = []
        for message in simulation_result.messages:
            messages.append({"agent": message.source, "message": message.content})

        output_variables = []
        information_return_agent_message = messages[-1]["message"]
        json_match = re.search(r'\{.*\}', information_return_agent_message, re.DOTALL)
        if json_match:
            try:
                parsed_json = json.loads(json_match.group(0))
                for variable in parsed_json:
                    # Handle both None and "Unspecified" values
                    value = parsed_json[variable]
                    if value is None or value == "Unspecified":
                        value = "Unspecified"
                    output_variables.append({"name": variable, "value": value})
            except json.JSONDecodeError:
                return None
        else:
            return None

        return {"messages": messages, "output_variables": output_variables}


    async def run(self):
        simulation_results = await Console(self.gc.run_stream())
        return self._process_result(simulation_results)