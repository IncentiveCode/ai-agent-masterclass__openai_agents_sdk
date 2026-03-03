import dotenv
dotenv.load_dotenv()

from openai import OpenAI
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

client = OpenAI()

if "agent" not in st.session_state:
	st.session_state["agent"] = Agent(
		name="life coach agent",
		instructions="""
			너는 매우 유능한 조력자야.

			너는 아래의 도구를 가지고 있어.
				- Web Search Tool: 이 도구를 사용해서 동기부여 컨텐츠, 자기 계발 팁, 습관 형성 조언을 검색하고 답변할 수 있어.
		""",
		tools=[
			WebSearchTool(),
		]
	)
agent = st.session_state["agent"]


if "session" not in st.session_state:
	st.session_state["session"] = SQLiteSession(
		"chat-history",
		"life-coach-agent-memory.db",
	)
session = st.session_state["session"]


async def print_history():
	messages = await session.get_items()

	for message in messages:
		if "role" in message:
			with st.chat_message(message["role"]):
				if message["role"] == "user":
					st.write(message["content"])
				else:
					if message["type"] == "message":
						st.write(message["content"][0]["text"].replace("$", "\\$"))

		if "type" in message:
			if message["type"] == "web_search_call":
				with st.chat_message("ai"):
					st.write("🔍 Searched the web...")
asyncio.run(print_history())



def update_status(status_container, event):
	status_messages = {
		"response.web_search_call.completed": (
			"✅ 웹 검색 완료", 
			"complete",
		),
		"response.web_search_call.in_progress": (
			"🔍 검색을 진행하고 있습니다...",
			"in-progress",
		),
		"response.web_search_call.searching": (
			"🔍 검색을 시작합니다...",
			"running",
		),
		"response.completed": (
			" ",
			"complete",
		),
	}

	if event in status_messages:
		label, state = status_messages[event]
		status_container.update(label=label, state=state)



async def run_agent(message):
	with st.chat_message("ai"):
		status_container = st.status("⏳", expanded=False)
		text_placeholder = st.empty()
		response = ""

		stream = Runner.run_streamed(
			agent,
			message,
			session=session,
		)

		async for event in stream.stream_events():
			if event.type == "raw_response_event":
				update_status(status_container, event.data.type)

				if event.data.type == "response.output_text.delta":
					response += event.data.delta
					text_placeholder.write(response.replace("$", "\\$"))


		
prompt = st.chat_input(
	"편하게 질문을 남겨주세요.",
)

if prompt:
	with st.chat_message("human"):
		st.write(prompt)
	asyncio.run(run_agent(prompt))



with st.sidebar:
	reset = st.button("메모리 초기화")
	if reset:
		asyncio.run(session.clear_session())
	st.write(asyncio.run(session.get_items()))