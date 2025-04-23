import asyncio
import os
import sys
from typing import Optional
from contextlib import AsyncExitStack
 
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
 
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
import json
 
load_dotenv()  # load environment variables from .env


def format_tools_for_llm(tool) -> str:
    """对tool进行格式化
    Returns:
        格式化之后的tool描述
    """
    args_desc = []
    if "properties" in tool.inputSchema:
        for param_name, param_info in tool.inputSchema["properties"].items():
            arg_desc = (
                f"- {param_name}: {param_info.get('description', 'No description')}"
            )
            if param_name in tool.inputSchema.get("required", []):
                arg_desc += " (required)"
            args_desc.append(arg_desc)
 
    return f"Tool: {tool.name}\nDescription: {tool.description}\nArguments:\n{chr(10).join(args_desc)}"
 
 
class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = AsyncOpenAI(
            base_url=os.getenv('BASE_URL'),
            api_key=os.getenv('API_KEY'),
        )
        self.model = os.getenv('MODEL_NAME')
        self.messages = []
 
    async def connect_to_server(self, server_script_path: str):
        """连接MCP服务器"""
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )
    
        self.stdio, self.write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        print('[debug] list tool ...')
        await self.session.initialize()
        print('[debug] initialize ...')
        # 列出可用工具
        response = await self.session.list_tools()
        tools = response.tools
        print("\n服务器中可用的工具：", [tool.name for tool in tools])
 
        tools_description = "\n".join([format_tools_for_llm(tool) for tool in tools])
        # 修改系统提示
        system_prompt = (
            "You are a helpful assistant with access to these tools:\n\n"
            f"{tools_description}\n"
            "Choose the appropriate tool based on the user's question. "
            "If no tool is needed, reply directly.\n\n"
            "IMPORTANT: When you need to use a tool, you must ONLY respond with "
            "the exact JSON object format below, nothing else:\n"
            "{\n"
            '    "tool": "tool-name",\n'
            '    "arguments": {\n'
            '        "argument-name": "value"\n'
            "    }\n"
            "}\n\n"
            '"```json" is not allowed'
            "After receiving a tool's response:\n"
            "1. Transform the raw data into a natural, conversational response\n"
            "2. Keep responses concise but informative\n"
            "3. Focus on the most relevant information\n"
            "4. Use appropriate context from the user's question\n"
            "5. Avoid simply repeating the raw data\n\n"
            "Please use only the tools that are explicitly defined above."
        )
        self.messages.append({"role": "system", "content": system_prompt})
 
    async def chat(self, prompt, role="user"):
        """与LLM进行交互"""
        self.messages.append({"role": role, "content": prompt})
 
        # 初始化 LLM API 调用
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
        )
        llm_response = response.choices[0].message.content
        return llm_response
 
    async def execute_tool(self, llm_response: str):
        """Process the LLM response and execute tools if needed.
        Args:
            llm_response: The response from the LLM.
        Returns:
            The result of tool execution or the original response.
        """
        import json
 
        try:
            tool_call = json.loads(llm_response.replace("```json\n", "").replace("```", ""))
            if "tool" in tool_call and "arguments" in tool_call:
                # result = await self.session.call_tool(tool_name, tool_args)
                response = await self.session.list_tools()
                tools = response.tools
 
                if any(tool.name == tool_call["tool"] for tool in tools):
                    try:
                        print("[提示]：正在执行函数")
                        result = await self.session.call_tool(
                            tool_call["tool"], tool_call["arguments"]
                        )
 
                        if isinstance(result, dict) and "progress" in result:
                            progress = result["progress"]
                            total = result["total"]
                            percentage = (progress / total) * 100
                            print(f"Progress: {progress}/{total} ({percentage:.1f}%)")
                        print(f"[执行结果]: {result}")
                        return f"Tool execution result: {result}"
                    except Exception as e:
                        error_msg = f"Error executing tool: {str(e)}"
                        print(error_msg)
                        return error_msg
 
                return f"No server found with tool: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response
 
 
    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("MCP 客户端启动")
        print("输入 /bye 退出")
 
        while True:
            prompt = input(">>> ").strip()
            if prompt.lower() == '/bye':
                break
 
            llm_response = await self.chat(prompt)
            print(llm_response)
 
            result = await self.execute_tool(llm_response)
 
            if result != llm_response:
                self.messages.append({"role": "assistant", "content": llm_response})
 
                final_response = await self.chat(result, "system")
                print(final_response)
                self.messages.append(
                    {"role": "assistant", "content": final_response}
                )
            else:
                self.messages.append({"role": "assistant", "content": llm_response})
 
 
async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run client.py <path_to_server_script>")
        sys.exit(1)
 
    client = MCPClient()
 
    await client.connect_to_server(sys.argv[1])
    await client.chat_loop()
 
 
if __name__ == "__main__":
    asyncio.run(main())