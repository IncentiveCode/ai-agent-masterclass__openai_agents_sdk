import dotenv
dotenv.load_dotenv()

from openai import OpenAI
import asyncio
import streamlit as st
from agents import Agent, FileSearchTool, Runner, SQLiteSession, WebSearchTool

client = OpenAI()
VECTOR_STORE_ID = "vs_69a6bc401228819188d002a71dfa5e06"

if "agent" not in st.session_state:
	st.session_state["agent"] = Agent(
		name="life coach agent",
		instructions="""
			너는 매우 유능한 조력자야.

			너는 아래의 도구를 가지고 있어.
				- Web Search Tool: 이 도구를 사용해서 동기부여 컨텐츠, 자기 계발 팁, 습관 형성 조언을 검색하고 답변할 수 있어.
				- File Search Tool: 너는 이 도구를 사용해서, 사용자가 특정 파일에 있는 내용에 관한 질문을 했을 때 파일을 확인하고 답변할 수 있어. 사용자에게 조언을 할 때도 첨부된 문서를 참조해서 조언해줘.
		""",
		tools=[
			WebSearchTool(),
			FileSearchTool(
				vector_store_ids=[VECTOR_STORE_ID],
				max_num_results=3
			),
		]
	)
agent = st.session_state["agent"]


if "session" not in st.session_state:
	st.session_state["session"] = SQLiteSession(
		"chat-history",
		"life-coach-agent-memory-2.db",
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
					st.write("🔍 웹 검색을 진행했습니다...")
			elif message["type"] == "file_search_call":
				with st.chat_message("ai"):
					st.write("🗂️ 파일 탐색을 진행했습니다...")
asyncio.run(print_history())



def update_status(status_container, event):
	status_messages = {
		"response.web_search_call.completed": (
			"✅ 웹 검색 완료", 
			"complete",
		),
		"response.web_search_call.in_progress": (
			"🔍 웹 검색을 진행하고 있습니다...",
			"running",
		),
		"response.web_search_call.searching": (
			"🔍 웹 검색을 시작합니다...",
			"running",
		),
		"response.file_search_call.completed": (
			"✅ 파일 검색 완료.",
			"complete",
		),
		"response.file_search_call.in_progress": (
			"🗂️ 파일 탐색을 진행하고 있습니다...",
			"running",
		),
		"response.file_search_call.searching": (
			"🗂️ 파일 탐색을 시작합니다...",
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
	accept_file="multiple",
	file_type=["txt"],
)

if prompt:
	for file in prompt.files:
		if (file.type.startswith("text/")):
			with st.chat_message("ai"):
				with st.status("⏳ Uploading file...") as status:
					uploaded_file = client.files.create(
						file=(file.name, file.getvalue()),
						purpose="user_data",
					)

					status.update(label="⏳ Attaching file...")
					client.vector_stores.files.create(
						vector_store_id=VECTOR_STORE_ID,
						file_id=uploaded_file.id,
					)

					status.update(label="✅ File uploaded", state="complete")

	if prompt.text:
		with st.chat_message("human"):
			st.write(prompt.text)
		asyncio.run(run_agent(prompt.text))



with st.sidebar:
	reset = st.button("메모리 초기화")
	if reset:
		asyncio.run(session.clear_session())
	st.write(asyncio.run(session.get_items()))