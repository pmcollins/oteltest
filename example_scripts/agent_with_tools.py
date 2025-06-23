from __future__ import annotations

"""
Agent with Tools example using LangChain with OpenTelemetry instrumentation.

Required packages:
pip install langchain langchain_openai langchain_community
"""

import datetime
import os

from zoneinfo import ZoneInfo  # For timezone-aware datetime


def run_agent_with_tools():
    """Run a simple agent with tools example."""

    from langchain.agents import AgentExecutor, create_react_agent
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.tools import Tool
    from langchain_openai import ChatOpenAI

    print("Creating LangChain agent with tools...")

    # Step 1: Define the tools
    tools = [
        Tool(
            name="CurrentWeather",
            description="Useful for getting the current weather in a specific location",
            func=get_current_weather,
        ),
        Tool(
            name="CurrentTime",
            description="Useful for getting the current date and time. This tool doesn't require any input.",
            func=lambda input_value: print(f"DEBUG - CurrentTime received input: '{input_value}'") or get_current_time(),  # Debug wrapper
        ),
        Tool(
            name="WebSearch",
            description="Useful for searching information on the web",
            func=search_web,
        ),
    ]

    # Step 2: Create the LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    # Step 3: Create the agent using ReAct framework
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant that has access to the following tools:
        
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question
"""),
        ("human", "{input}"),
        ("ai", "{agent_scratchpad}"),
    ])

    agent = create_react_agent(llm, tools, prompt)

    # Step 4: Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )

    # Step 5: Run the agent with different queries
    questions = [
        "What's the weather like in San Francisco?",
        "What time is it right now?",
        "Can you search for information about LangChain?",
    ]

    for question in questions:
        print(f"\nQuestion: {question}")
        result = agent_executor.invoke({"input": question})
        print(f"Final Answer: {result['output']}")


def get_current_weather(location):
    """Get the current weather in a given location.

    This is a mock function that would normally call a weather API.
    For demo purposes, we just return a hard-coded response.

    Args:
        location: The city and state, e.g. San Francisco, CA

    Returns:
        String containing weather information
    """
    # In a real implementation, this would call a weather API
    return f"The current weather in {location} is 72°F and sunny."


def get_current_time():
    """Get the current time.

    Returns:
        String with the current time
    """
    now = datetime.datetime.now(tz=ZoneInfo("UTC"))
    return f"The current time is {now.strftime('%H:%M:%S')} on {now.strftime('%Y-%m-%d')}."


def search_web(query):
    """Mock web search function.

    Args:
        query: The search query

    Returns:
        String with search results
    """
    # In a real implementation, this would call a search API
    return f"Here are the top results for '{query}': (1) Mock result 1 (2) Mock result 2"


def main():
    run_agent_with_tools()


if __name__ == "__main__":
    main()


class OtelTest:
    def environment_variables(self):
        return {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        }

    def requirements(self):
        return [
            "urllib3<2.0", "langchain", "langchain-openai", "langchain-community",
            "opentelemetry-distro[otlp]", "faiss-cpu",
            "/Users/pabcolli/github/zhirafovod/opentelemetry-python-contrib/"
            "instrumentation-genai/opentelemetry-instrumentation-langchain"
        ]

    def is_http(self) -> bool:
        return False

    def wrapper_command(self) -> str:
        return "opentelemetry-instrument"

    def on_start(self):
        return None

    def on_stop(self, tel, stdout: str, stderr: str, returncode: int) -> None:
        return None
