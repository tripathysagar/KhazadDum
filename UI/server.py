# ============ IMPORTS ============
from fastcore.all import *
from fasthtml.common import *
from fasthtml.jupyter import *
import fasthtml.components as fh
import httpx
import mistletoe
from toolslm.shell import get_shell

#---
from litellm.types.utils import Message
from KhazadDum.SnowflakeCore import *
from KhazadDum.AgentV1 import *
from KhazadDum.ChatDB import *
from KhazadDum.Chatloop import *

#==================
agent = SnowflakeAgent()

M1 = DBMetadata(
    agent,
    "AIRLINES", "AIRLINES", model_name = model_name)


assert hasattr(M1, "agent")
assert not hasattr(M1, "metadata")
assert M1()
assert hasattr(M1, "metadata")

SYSTEM_PROMPT = create_system_prompt(M1.metadata)

loop = ChatLoop(
    DB,
    model_name, 
    sp=SYSTEM_PROMPT,
    tools=[agent.execute_query],
)


# ============ SETUP ============
# DaisyUI styling headers
daisy_hdrs = (
    Link(href='https://cdn.jsdelivr.net/npm/daisyui@5', rel='stylesheet', type='text/css'),
    Script(src='https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4'),
    Link(href='https://cdn.jsdelivr.net/npm/daisyui@5/themes.css', rel='stylesheet', type='text/css')
)

# FastHTML app and route decorator
app = FastHTML(hdrs=daisy_hdrs)
rt = app.route

# Preview helper for Jupyter
def get_preview(app):
    return partial(HTMX, app=app, host=None, port=None)
preview = get_preview(app)


# Shell for code execution
sh = get_shell()

# ============ STATE MANAGEMENT ============
class ChatState:
    """Holds all chat state: messages, history, and current conversation ID"""
    def __init__(self):
        self.formatted_msg = []                  # Current conversation as list of dicts
        self.hist = loop.db.get_chat_list()     # All saved conversations {conv_id: [messages]}
        self.conv_id = 0                         # Current conversation ID
        self.user_idx = []
        self.assi_idx = []



STATE = ChatState()

def get_user_idx(): 
    """Find the indexes with user role"""
    result = []
    for i, c in enumerate(STATE.formatted_msg):
        # Handle both dict and Message objects
        if isinstance(c, dict):
            role = c.get('role')
        else:
            role = getattr(c, 'role', None)
        
        if role == 'user':
            result.append(i)
    return result


def get_assi_idx():
    """Find the indexes with assistant role"""
    temp = (STATE.user_idx[1:] if len(STATE.user_idx) != 1 else []) + [len(STATE.formatted_msg)]
    return [i - 1 for i in temp]

# ============ CODE EXECUTION ============
def run(code: str):
    """Execute Python code and return (result, details_dict)"""
    r = sh.run_cell(code)
    details = dict(
        result=r.result,
        stdout=r.stdout,
        error_in_exec=r.error_in_exec,
        error_before_exec=r.error_before_exec,
    )

    if r.error_before_exec:
        return str(r.error_before_exec), details
    if r.error_in_exec:
        return str(r.error_in_exec), details
    
    return r.result, details

# ============ MARKDOWN HELPERS ============
def details_to_md(d: dict) -> str:
    """Convert details dict to markdown list"""
    r = ""
    for k, v in d.items():
        r += f"\n1. **{k}** : {v}"
    return r

# ============ CHAT COMPONENTS ============
def UserChat(msg: str):
    """Render a user message bubble (left-aligned)"""
    return Div(
        Div(
            Div('👤', cls='text-3xl bg-base-200'),
            cls='chat-image avatar'
        ),
        Div(msg['content'], cls='chat-bubble'),
        cls='chat chat-start'
    )

"""
Details(
            Summary('details', cls='cursor-pointer text-xs opacity-50'),
            Div(
                NotStr(html_str),
                cls='card bg-base-200 h-32 max-w-xs overflow-y-auto overflow-x-hidden p-2 text-xs break-words whitespace-pre-wrap'
            ),
            cls='chat-footer'
        ),
"""

def extract_turn_details(assistant_idx):
    """Extract all intermediate steps for this conversation turn"""
    steps = []
    
    # Walk backwards from assistant message to find all intermediate messages
    for i in range(assistant_idx - 1, -1, -1):
        msg = loop.all_hist[i]
        msg_dict = msg.model_dump() if isinstance(msg, Message) else msg
        
        role = msg_dict.get('role')
        
        # Stop when we hit the user question
        if role == 'user':
            break
        
        # Collect intermediate assistant and tool messages
        if role == 'assistant':
            # Check for reasoning
            if msg_dict.get('reasoning_content'):
                steps.insert(0, ('reasoning', msg_dict.get('reasoning_content')))
            
            # Check for tool calls
            if msg_dict.get('tool_calls'):
                for tc in msg_dict['tool_calls']:
                    func_name = tc.get('function', {}).get('name', 'unknown')
                    func_args = tc.get('function', {}).get('arguments', '{}')
                    steps.insert(0, ('tool_call', f"{func_name}({func_args})"))
        
        elif role == 'tool':
            tool_name = msg_dict.get('name', 'unknown')
            tool_output = msg_dict.get('content', '')
            steps.insert(0, ('tool_response', f"**{tool_name}:**\n```\n{tool_output}\n```"))
    
    return steps

def AssistantChat(result, msg_idx=None):
    """Render an assistant message bubble (right-aligned) with collapsible details"""
    content = result.get('content', '') if isinstance(result, dict) else str(result)
    
    # Convert markdown to HTML
    html_content = mistletoe.markdown(content)
    
    # Build basic bubble
    bubble_content = [
        Div(
            Div('🤖', cls='text-3xl bg-base-200'),
            cls='chat-image avatar'
        ),
        Div(NotStr(html_content), cls='chat-bubble')
    ]
    
    # Add details section if we have message index
    if msg_idx is not None:
        steps = extract_turn_details(msg_idx)
        
        if steps:
            details_parts = []
            turn_num = 1
            current_assistant = []
            
            for step_type, step_content in steps:
                if step_type == 'reasoning':
                    current_assistant.append(f"- **Reasoning:** {step_content}")
                elif step_type == 'tool_call':
                    current_assistant.append(f"- **Tool Call:** 🔧 `{step_content}`")
                elif step_type == 'tool_response':
                    # If we have accumulated assistant actions, add them first
                    if current_assistant:
                        details_parts.append(f"### 🤖 Assistant Action {turn_num}\n" + "\n".join(current_assistant))
                        current_assistant = []
                    
                    # Add tool response
                    details_parts.append(f"### 📋 Tool Response {turn_num}\n{step_content}")
                    turn_num += 1
            
            # Add any remaining assistant actions (shouldn't happen normally)
            if current_assistant:
                details_parts.append(f"### 🤖 Assistant Action {turn_num}\n" + "\n".join(current_assistant))
            
            details_md = "\n\n---\n\n".join(details_parts)
            details_html = mistletoe.markdown(details_md)
            
            bubble_content.append(
                Details(
                    Summary('details', cls='cursor-pointer text-xs opacity-50'),
                    Div(
                        NotStr(details_html),
                        cls='card bg-base-200 h-auto max-h-64 max-w-2xl overflow-y-auto overflow-x-auto p-2 text-xs break-words whitespace-pre-wrap'
                    ),
                    cls='chat-footer'
                )
            )
    
    return Div(*bubble_content, cls='chat chat-end')
    
def render_msgs():
    """Convert ChatLoop history to rendered chat elements"""
    rendered = []
    
    for idx, msg in enumerate(loop.all_hist):
        # Convert Message to dict if needed
        if isinstance(msg, Message):
            msg = msg.model_dump()
        
        role = msg.get('role')
        
        if role == 'user':
            rendered.append(UserChat(msg))
        elif role == 'assistant' and msg.get('content'):
            # Pass the index so we can extract turn details
            rendered.append(AssistantChat(msg, msg_idx=idx))
        # Skip tool messages and assistant messages without content
    
    return rendered

# ============ STATE OPERATIONS ============
def save_msg():
    """Save current conversation to history and reset for new conversation"""
    if len(STATE.formatted_msg) <= 0:
        return

    STATE.hist[STATE.conv_id] = STATE.formatted_msg
    STATE.conv_id = len(STATE.hist)  # Next new conversation ID
    STATE.formatted_msg = []

# ============ UI COMPONENTS ============
@rt
def Header():
    """Top navigation bar with title and new chat button"""
    return Div(
        Div('🤖 Code Chat', cls='text-xl font-bold'),
        Button('+ New Chat', cls='btn btn-primary btn-sm', hx_post=new_chat, hx_swap='none'),
        cls='navbar bg-base-300 px-4 flex justify-between'
    )

def Sidebar():
    """Left sidebar showing conversation history"""
    # Fetch fresh history from database
    history = loop.db.get_chat_list()
    
    return Div(
        Div('History', cls='text-lg font-bold mb-2'),
        Div(
            *[Button(
                 hist['title'][:30] + '...' if len(hist['title']) > 30 else hist['title'], 
                 cls=f'btn btn-sm btn-block text-left truncate {"btn-accent" if hist["chat_id"] == STATE.conv_id else "btn-primary"}', 
                 hx_get=f'/load_chat/{hist["chat_id"]}', 
                 hx_swap='none',
                 title=hist['title']  # Show full title on hover
              ) 
              for hist in history],  # Newest first
            cls='flex flex-col gap-2 overflow-y-auto flex-1'
        ),

        cls='w-64 bg-base-200 p-4 h-full flex flex-col',
        id='sidebar',
        hx_swap_oob='true'
    )

def MainChat():
    """Main chat area with messages and input form"""
    return Div(
        Div(*render_msgs(), id='test', cls='flex flex-col flex-1 overflow-y-auto p-4 min-h-0'),
        Form(hx_post='/send_message', hx_target='#test', hx_swap='beforeend show:bottom')(
            Div(
                Input(type='text', placeholder='Type here', id='inp', cls='input flex-1 input-secondary', name='qn', required=True),
                Button('Ask', type='submit', cls='btn btn-primary', id='ask-btn'),
                cls='flex gap-2 p-4'
            )
        ),
        cls='flex flex-col flex-1'
    )

@rt
def index():
    """Main window layout combining header, sidebar, and chat"""
    return Div(data_theme='synthwave')(
        Header(),
        Div(
            Sidebar(),
            MainChat(),
            cls='flex flex-1 h-[calc(100vh-64px)]'
        ),
        cls='flex flex-col h-screen'
    )

# ============ ROUTES ============
@rt('/send_message')
def send_message(qn: str):
    """Immediately show user message and clear input, trigger async LLM processing"""
    print(f"[DEBUG] Received question: {qn}")
    
    # Validate input - ignore empty or whitespace-only messages
    if not qn or not qn.strip():
        return Div()  # Return empty div, do nothing
    
    # Show user message bubble
    uc = UserChat({'content': qn})
    
    # Clear input field
    cleared_input = Input(type='text', placeholder='Type here', id='inp', value='', 
                         cls='input flex-1 input-secondary', name='qn', hx_swap_oob='true')
    
    # Disable the Ask button while processing
    disabled_btn = Button('Processing...', type='submit', cls='btn btn-primary', id='ask-btn', 
                         disabled=True, hx_swap_oob='true')
    
    # Create a div that will trigger the LLM processing
    # This div loads immediately and fetches the assistant response
    from urllib.parse import quote
    trigger_div = Div(
        hx_get=f'/process_response?qn={quote(qn)}',
        hx_trigger='load',
        hx_swap='outerHTML'
    )
    
    return uc, cleared_input, disabled_btn, trigger_div

@rt('/process_response')
def process_response(qn: str):
    """Process LLM call and return assistant response"""
    try:
        # Send to ChatLoop (limit steps to prevent hanging)
        print("[DEBUG] Calling loop...")
        response = loop(qn, max_steps=10)
        print(f"[DEBUG] Got response: {type(response)}")
        
        # Get final assistant content from history
        final_content = None
        lis = loop.json
        if lis[-1]['role'] == 'assistant':
            final_content = lis[-1]['content']
        
        if not final_content:
            final_content = "I processed your request but didn't generate a response."
        
        print(f"[DEBUG] Final content: {final_content}")
        
        # Pass the index of the last message to render details
        last_msg_idx = len(loop.all_hist) - 1
        ac = AssistantChat({'content': final_content}, msg_idx=last_msg_idx)
        
        # Re-enable the Ask button
        enabled_btn = Button('Ask', type='submit', cls='btn btn-primary', id='ask-btn', 
                            hx_swap_oob='true')
        
        print("[DEBUG] Returning response")
        return ac, enabled_btn
    
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        
        # Return error message
        enabled_btn = Button('Ask', type='submit', cls='btn btn-primary', id='ask-btn', 
                            hx_swap_oob='true')
        return AssistantChat({'content': f"Error: {str(e)}"}), enabled_btn
@rt
def new_chat():
    """Start a new conversation: clear ChatLoop, update UI"""
    loop.new_chat()  # Reset ChatLoop state
    STATE.conv_id = None  # Reset active conversation ID
    return (Div(*render_msgs(), id='test', cls='flex flex-col flex-1 overflow-y-auto p-4', hx_swap_oob='true'), 
            Sidebar())

@rt('/load_chat/{cid}')
def load_chat(cid: int):
    """Load a conversation from history by ID"""
    #save_msg()  # Save ongoing conversation first

    chat_ids = [i['chat_id']for i in loop.db.get_chat_list()]

    if cid not in chat_ids:
        return new_chat()  # Invalid ID, start fresh

    loop.chat_id = None

    STATE.conv_id = cid
    STATE.formatted_msg = loop.load_session(cid)  # Copy to avoid mutation
    print(STATE.formatted_msg )
    STATE.user_idx = get_user_idx()
    STATE.assi_idx = get_assi_idx()
    
    return (Div(*render_msgs(), id='test', cls='flex flex-col flex-1 overflow-y-auto p-4', hx_swap_oob='true'), 
            Sidebar())

# ============ RUN ============
if __name__ == "__main__":
    serve(host="0.0.0.0", port=8000, reload=True)
