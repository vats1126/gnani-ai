import asyncio
import logging
import re
from typing import Optional, Tuple, List, Dict, Any
from app.config import settings
from app.schemas import TutorTurnRequest, TutorTurnResponse, VerdictType
from app.services.session_manager import SessionRecord
from app.tools.math_verifier import verify_equation_step
from app.tools.practice_generator import generate_practice_question

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are an expert, encouraging, Socratic Multilingual Learning Tutor for school students in India.
Your mission is to guide learners to discover answers on their own, never giving away the final answer outright.

Pedagogical Guidelines:
1. Socratic Method: Ask guiding questions. Break complex problems into smaller, manageable steps. Give one small hint at a time.
2. Whiteboard Awareness: Pay close attention to what the student has drawn or written on the whiteboard image. Refer to their handwritten equations, numbers, and diagrams directly.
3. Multilingual Communication: Reply in the student's selected language (or match their spoken/typed language if Auto-detect is chosen). Keep mathematical equations, formulas, and variables in standard international notation (e.g. 2x + 5 = 15, x = 5) so they remain universally readable.
4. Simplicity & Analogies: When asked to explain simply, use intuitive everyday analogies (e.g., fruits, pocket money, balance scales).
5. Mathematical Rigor: Never confirm a student's step as definitively correct unless verified by the CAS verifier tool. When checking a student's work on an equation, always use the verify_equation_step tool to confirm whether the step is mathematically sound. Explain the result warmly and socratically.
6. Practice Generation: When the student asks for practice or finishes a problem, use the generate_practice_question tool to suggest a fresh problem.
7. Tone: Warm, patient, curious, and respectful. Celebrate effort and curiosity.
"""


class GeminiNotConfiguredError(Exception):
    """Raised when GEMINI_API_KEY is not configured or placeholder."""
    pass


class GeminiProviderError(Exception):
    """Raised when upstream Gemini communication fails completely across all tiers."""
    pass


def is_rate_limit_error(e: Exception) -> bool:
    """Detects 429 / Quota / ResourceExhausted errors."""
    msg = str(e).lower()
    return "429" in msg or "resource_exhausted" in msg or "quota" in msg or getattr(e, "code", None) == 429


def get_gemini_tools():
    """Builds the tool declarations for Gemini function calling."""
    from google.genai import types

    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="verify_equation_step",
                    description=(
                        "Deterministically verifies whether a student's algebraic step or equation is "
                        "mathematically equivalent and valid compared to the previous step or original "
                        "equation using Computer Algebra System (CAS). Call this whenever a student asks "
                        "to check their work or step, or whenever you evaluate an equation step."
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "original_equation": types.Schema(
                                type="STRING",
                                description="The starting or original equation (e.g. '2x = 8' or '2x + 5 = 15')"
                            ),
                            "previous_step": types.Schema(
                                type="STRING",
                                description="The intermediate step immediately preceding current_step (optional)"
                            ),
                            "current_step": types.Schema(
                                type="STRING",
                                description="The student's new equation step to verify (e.g. 'x = 8' or '2x = 10')"
                            ),
                            "variable": types.Schema(
                                type="STRING",
                                description="The variable being solved for (default 'x')"
                            ),
                        },
                        required=["original_equation", "current_step"]
                    )
                ),
                types.FunctionDeclaration(
                    name="generate_practice_question",
                    description=(
                        "Generates a fresh school-level mathematics or science practice problem "
                        "for the student to solve on the whiteboard."
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "topic": types.Schema(
                                type="STRING",
                                description="Topic name (e.g. 'linear_equations' or 'science')"
                            ),
                            "difficulty": types.Schema(
                                type="STRING",
                                description="Difficulty level ('easy' or 'medium')"
                            ),
                            "language": types.Schema(
                                type="STRING",
                                description="Indic language code (e.g. 'en-IN', 'hi-IN')"
                            ),
                        }
                    )
                )
            ]
        )
    ]


def extract_equations_from_message(text: str) -> Optional[Tuple[str, str]]:
    """
    Extracts equation pairs from typed student text (e.g. '2x = 8, x = 8' or 'Is 2x = 8 and x = 4 correct?').
    """
    if not text:
        return None
    clauses = re.split(r"[,;\n]|\band\b", text, flags=re.IGNORECASE)
    eqs = []
    for c in clauses:
        if "=" in c:
            parts = c.split("=")
            if len(parts) == 2:
                lhs = re.sub(r"^[^\d\w]*[a-zA-Z]+(?:\s+[a-zA-Z]+)*\s+", "", parts[0].strip()).strip()
                rhs = re.sub(r"\s+[a-zA-Z]+(?:\s+[a-zA-Z]+)*[^\d\w]*$", "", parts[1].strip()).strip()
                rhs = rhs.rstrip("?.,!")
                if lhs and rhs:
                    eqs.append(f"{lhs} = {rhs}")
    if len(eqs) >= 2:
        return eqs[0], eqs[1]
    return None


def build_turn_prompt(request: TutorTurnRequest, history_summary: str = "") -> str:
    parts = []

    # Language guidance
    if request.language_code and request.language_code != "indic-auto":
        parts.append(f"[Language Instruction: Respond in locale {request.language_code} while keeping mathematical equations and symbols in standard international notation.]")
    else:
        parts.append("[Language Instruction: Respond in the student's language or clear Indian English if uncertain, while keeping mathematical formulas in standard notation.]")

    # Subject & Action guidance
    parts.append(f"[Subject: {request.subject.upper()} | Learner Level: {request.learner_level}]")

    if request.action == "hint":
        parts.append("[Intent: HINT. Give exactly ONE small Socratic hint that encourages the immediate next thinking step. Do NOT give the final solution.]")
    elif request.action == "explain_simply":
        parts.append("[Intent: EXPLAIN SIMPLY. Use an intuitive, everyday real-world analogy to make this concept easy to understand.]")
    elif request.action == "check_work":
        parts.append("[Intent: CHECK WORK. Inspect the handwritten steps on the whiteboard or text. You MUST call the verify_equation_step tool to confirm whether the step is mathematically valid before answering.]")
    elif request.action == "practice":
        parts.append("[Intent: PRACTICE. Provide a similar, engaging practice question based on the board concept using the generate_practice_question tool.]")

    # Context history for transparent recovery
    if history_summary:
        parts.append(f"\n[Recent Context]\n{history_summary}\n")

    # Student message
    student_msg = request.message.strip() if request.message else "(Student provided the whiteboard image for review)"
    parts.append(f"Student: {student_msg}")

    return "\n".join(parts)


async def connect_live_session(record: SessionRecord, model_name: Optional[str] = None):
    """Establishes a new live Gemini connection session with tool declarations."""
    from google import genai
    from google.genai import types

    chosen_model = model_name or settings.GEMINI_LIVE_MODEL
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options={"api_version": "v1alpha"}
    )
    tools = get_gemini_tools()
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.TEXT],
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=SYSTEM_INSTRUCTION)]
        ),
        tools=tools,
    )

    cm = client.aio.live.connect(model=chosen_model, config=config)
    session = await cm.__aenter__()
    record.live_cm = cm
    record.live_session = session
    return session


async def _send_and_receive(session, parts) -> Tuple[str, Optional[str], List[str], Optional[str]]:
    """
    Sends multimodal parts and receives the response over Gemini Live, executing tool calls.
    Returns: (answer_text, captured_verdict, captured_steps, captured_next_step)
    """
    from google.genai import types

    await session.send(input=parts, end_of_turn=True)

    response_chunks = []
    captured_verdict: Optional[str] = None
    captured_steps: List[str] = []
    captured_next_step: Optional[str] = None

    async with asyncio.timeout(15.0):
        async for response in session.receive():
            # 1. Handle Tool Calls
            if response.tool_call and response.tool_call.function_calls:
                fn_responses = []
                for fc in response.tool_call.function_calls:
                    call_name = fc.name
                    call_id = fc.id
                    call_args = fc.args or {}
                    logger.info(f"Gemini Live invoked tool: '{call_name}' with args {call_args}")

                    if call_name == "verify_equation_step":
                        result = verify_equation_step(
                            original_equation=call_args.get("original_equation", ""),
                            previous_step=call_args.get("previous_step", ""),
                            current_step=call_args.get("current_step", ""),
                            variable=call_args.get("variable", "x")
                        )
                        captured_verdict = result["status"]
                        captured_steps.append(result["reason"])
                        if result.get("expected_next_step"):
                            captured_next_step = result["expected_next_step"]

                        fn_responses.append(
                            types.FunctionResponse(name=call_name, id=call_id, response=result)
                        )

                    elif call_name == "generate_practice_question":
                        result = generate_practice_question(
                            topic=call_args.get("topic", "linear_equations"),
                            difficulty=call_args.get("difficulty", "easy"),
                            language=call_args.get("language", "en-IN")
                        )
                        captured_steps.append(f"Practice Question: {result['question']}")
                        if result.get("hint"):
                            captured_next_step = result["hint"]

                        fn_responses.append(
                            types.FunctionResponse(name=call_name, id=call_id, response=result)
                        )

                    else:
                        fn_responses.append(
                            types.FunctionResponse(
                                name=call_name,
                                id=call_id,
                                response={"error": f"Tool '{call_name}' not recognized"}
                            )
                        )

                # Return tool results back to Gemini Live session
                await session.send_tool_response(function_responses=fn_responses)

            # 2. Handle Text Content
            server_content = response.server_content
            if server_content is not None and server_content.model_turn is not None:
                for part in server_content.model_turn.parts:
                    if part.text:
                        response_chunks.append(part.text)

            if server_content and server_content.turn_complete:
                break

    answer_text = "".join(response_chunks).strip()
    return answer_text, captured_verdict, captured_steps, captured_next_step


# =====================================================================
# TIER 1: Gemini Live WebSocket Execution
# =====================================================================
async def _execute_tier1_live(
    request: TutorTurnRequest,
    record: SessionRecord,
    turn_parts: list
) -> Tuple[str, Optional[str], List[str], Optional[str]]:
    """Attempts turn via Gemini Live WebSocket using primary or fallback live model."""
    models_to_try = [settings.GEMINI_LIVE_MODEL]
    if settings.GEMINI_LIVE_MODEL != "gemini-2.0-flash-live-001":
        models_to_try.append("gemini-2.0-flash-live-001")

    last_error = None
    for model_name in models_to_try:
        try:
            if record.live_session is None:
                await connect_live_session(record, model_name=model_name)

            answer, verdict, steps, next_step = await _send_and_receive(record.live_session, turn_parts)
            if answer or verdict:
                return answer, verdict, steps, next_step
        except Exception as e:
            last_error = e
            logger.warning(f"Tier 1 (Live {model_name}) attempt failed: {e}. Closing live session...")
            await record.close_live()
            if is_rate_limit_error(e):
                # Do not loop retries on 429
                raise e

    raise last_error or Exception("Tier 1 Live failed")


# =====================================================================
# TIER 2: Multimodal generate_content Fallback
# =====================================================================
async def _execute_tier2_generate_content(
    request: TutorTurnRequest,
    image_bytes: Optional[bytes],
    prompt_text: str
) -> Tuple[str, Optional[str], List[str], Optional[str]]:
    """Fallback using standard multimodal generate_content (gemini-3.5-flash -> gemini-3.8-flash -> gemini-3.7-flash)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    models_to_try = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.7-flash"]

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=get_gemini_tools(),
        temperature=0.7,
    )

    contents: list = []
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    contents.append(types.Part.from_text(text=prompt_text))

    last_error = None
    for model_name in models_to_try:
        try:
            logger.info(f"Tier 2: Attempting generate_content with model '{model_name}'...")
            res = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                ),
                timeout=15.0
            )

            captured_verdict: Optional[str] = None
            captured_steps: List[str] = []
            captured_next_step: Optional[str] = None
            answer_text = ""

            # Check for function calls
            if res.function_calls:
                fn_parts = []
                for fc in res.function_calls:
                    call_name = fc.name
                    call_args = fc.args or {}
                    logger.info(f"Tier 2 ({model_name}) tool call: '{call_name}' with {call_args}")

                    if call_name == "verify_equation_step":
                        v_res = verify_equation_step(
                            original_equation=call_args.get("original_equation", ""),
                            previous_step=call_args.get("previous_step", ""),
                            current_step=call_args.get("current_step", ""),
                            variable=call_args.get("variable", "x")
                        )
                        captured_verdict = v_res["status"]
                        captured_steps.append(v_res["reason"])
                        if v_res.get("expected_next_step"):
                            captured_next_step = v_res["expected_next_step"]
                        fn_parts.append(
                            types.Part.from_function_response(name=call_name, response={"result": v_res})
                        )

                    elif call_name == "generate_practice_question":
                        pq_res = generate_practice_question(
                            topic=call_args.get("topic", "linear_equations"),
                            difficulty=call_args.get("difficulty", "easy"),
                            language=call_args.get("language", "en-IN")
                        )
                        captured_steps.append(f"Practice Question: {pq_res['question']}")
                        if pq_res.get("hint"):
                            captured_next_step = pq_res["hint"]
                        fn_parts.append(
                            types.Part.from_function_response(name=call_name, response={"result": pq_res})
                        )

                # Send function responses for final verbal synthesis
                if fn_parts:
                    followup_contents = list(contents)
                    # Add model's tool calls
                    if res.candidates and res.candidates[0].content:
                        followup_contents.append(res.candidates[0].content)
                    followup_contents.append(types.Content(parts=fn_parts))

                    try:
                        followup_res = await asyncio.wait_for(
                            client.aio.models.generate_content(
                                model=model_name,
                                contents=followup_contents,
                                config=config,
                            ),
                            timeout=10.0
                        )
                        if followup_res.text:
                            answer_text = followup_res.text.strip()
                    except Exception as fe:
                        logger.warning(f"Tier 2 follow-up text generation failed: {fe}")

            if not answer_text and res.text:
                answer_text = res.text.strip()

            if answer_text or captured_verdict:
                return answer_text, captured_verdict, captured_steps, captured_next_step

        except Exception as e:
            last_error = e
            logger.warning(f"Tier 2 ({model_name}) failed: {e}")
            if is_rate_limit_error(e):
                # Don't loop retries on 429
                continue

    raise last_error or Exception("Tier 2 generate_content failed")


# =====================================================================
# TIER 3: Emergency Local Rescue (Offline / Quota-Exhausted Demo Shield)
# =====================================================================
def _execute_tier3_emergency_rescue(
    request: TutorTurnRequest,
    record: SessionRecord
) -> Tuple[str, VerdictType, List[str], Optional[str]]:
    """
    Emergency rescue when all Gemini tiers fail or rate-limit.
    Deterministically evaluates equations via SymPy CAS and synthesizes
    localized Socratic feedback without crashing the live demo.
    """
    logger.warning("Tier 3 Emergency Rescue triggered: evaluating locally via CAS & Socratic heuristics.")

    lang = request.language_code if request.language_code and request.language_code != "indic-auto" else "en-IN"
    lang_prefix = lang.split("-")[0].lower()

    # 1. Check for equations in message or check_work action
    eq_pair = extract_equations_from_message(request.message)
    captured_verdict: VerdictType = "not_applicable"
    captured_steps: List[str] = []
    captured_next_step: Optional[str] = None
    answer_text = ""

    if eq_pair:
        orig, curr = eq_pair
        res = verify_equation_step(original_equation=orig, current_step=curr)
        captured_verdict = res["status"]
        captured_steps.append(res["reason"])
        captured_next_step = res.get("expected_next_step")

        if captured_verdict == "correct":
            templates = {
                "hi": f"शानदार! आपका कदम '{curr}' गणितीय रूप से सही है। {res.get('expected_next_step', '')}",
                "kn": f"ಅದ್ಭುತ! ನಿಮ್ಮ ಹಂತ '{curr}' ಗಣಿತದ ದೃಷ್ಟಿಯಿಂದ ಸರಿಯಾಗಿದೆ. {res.get('expected_next_step', '')}",
                "ta": f"அருமை! உங்கள் படி '{curr}' கணித ரீதியாக சரியானது. {res.get('expected_next_step', '')}",
                "te": f"చాలా బాగుంది! మీ సమీకరణం '{curr}' గణితపరంగా సరైనది. {res.get('expected_next_step', '')}",
                "en": f"Great job! Your step '{curr}' is mathematically verified as correct. {res.get('expected_next_step', '')}",
            }
            answer_text = templates.get(lang_prefix, templates["en"])
        elif captured_verdict == "incorrect":
            templates = {
                "hi": f"आइए आपके कदम की जांच करें: {res['reason']} {res.get('expected_next_step', '')}",
                "kn": f"ನಿಮ್ಮ ಹಂತವನ್ನು ಪರಿಶೀಲಿಸೋಣ: {res['reason']} {res.get('expected_next_step', '')}",
                "ta": f"உங்கள் படியைச் சரிபார்ப்போம்: {res['reason']} {res.get('expected_next_step', '')}",
                "te": f"మీ సమీకరణాన్ని పరిశీలిద్దాం: {res['reason']} {res.get('expected_next_step', '')}",
                "en": f"Let's look closer at your step: {res['reason']} {res.get('expected_next_step', '')}",
            }
            answer_text = templates.get(lang_prefix, templates["en"])
        else:
            answer_text = f"I checked your equation: {res['reason']}"

    elif request.action == "practice":
        pq = generate_practice_question(request.subject, "easy", lang)
        captured_steps.append(f"Practice Question: {pq['question']}")
        captured_next_step = pq.get("hint")
        answer_text = f"{pq['question']}\n\n{pq.get('hint', '')}"

    elif request.action == "hint":
        hints = {
            "hi": "संकेत: चर (x) को अलग करने के लिए समीकरण के दोनों पक्षों पर एक ही गणितीय संक्रिया करें।",
            "kn": "ಸುಳಿವು: ಚರಾಂಶವನ್ನು (x) ಪ್ರತ್ಯೇಕಿಸಲು ಸಮೀಕರಣದ ಎರಡೂ ಬದಿಗಳಲ್ಲಿ ಒಂದೇ ಗಣಿತದ ಕ್ರಿಯೆಯನ್ನು ಮಾಡಿ.",
            "ta": "குறிப்பு: மாறியை (x) தனிமைப்படுத்த சமன்பாட்டின் இருபுறமும் ஒரே கணித செயல்பாட்டைச் செய்யுங்கள்.",
            "te": "సూచన: చలరాశిని (x) వేరు చేయడానికి సమీకరణం యొక్క రెండు వైపులా ఒకే గణిత చర్యను చేయండి.",
            "en": "Socratic Hint: Look at what is attached to the variable. What operation can you apply to BOTH sides of the equals sign to isolate it?",
        }
        answer_text = hints.get(lang_prefix, hints["en"])
        captured_next_step = "Try applying this operation on the whiteboard!"

    elif request.action == "explain_simply":
        explanations = {
            "hi": "समीकरण को एक तराजू की तरह समझें। तराजू को संतुलित रखने के लिए जो भी आप बाईं ओर जोड़ते, घटाते या गुणा करते हैं, वही आपको दाईं ओर भी करना होगा!",
            "kn": "ಸಮೀಕರಣವನ್ನು ತಕ್ಕಡಿಯಂತೆ ಊಹಿಸಿ. ತಕ್ಕಡಿಯನ್ನು ಸಮತೋಲನದಲ್ಲಿಡಲು, ನೀವು ಎಡಭಾಗದಲ್ಲಿ ಏನು ಮಾಡುತ್ತೀರೋ, ಅದನ್ನೇ ಬಲಭಾಗದಲ್ಲೂ ಮಾಡಬೇಕು!",
            "ta": "சமன்பாட்டை ஒரு தராசு போல நினையுங்கள். சமநிலையை பராமரிக்க இடதுபுறத்தில் நீங்கள் எதைச் செய்தாலும், அதையே வலதுபுறத்திலும் செய்ய வேண்டும்!",
            "te": "సమీకరణాన్ని ఒక త్రాసుగా భావించండి. బ్యాలెన్స్ ఉంచడానికి మీరు ఎడమవైపు ఏమి చేసినా, కుడివైపు కూడా అదే చేయాలి!",
            "en": "Think of an equation like a balanced scale. Whatever operation you do to one side (add, subtract, multiply, divide), you must do the exact same thing to the other side to keep it perfectly balanced!",
        }
        answer_text = explanations.get(lang_prefix, explanations["en"])
        captured_next_step = "Would you like to try a practice problem to see this in action?"

    elif request.subject == "science":
        science_answers = {
            "hi": "विज्ञान में याद रखें: द्रव्यमान (Mass) किसी वस्तु में पदार्थ की मात्रा है, जबकि भार (Weight) उस पर लगने वाला गुरुत्वाकर्षण बल है: W = m * g।",
            "kn": "ವಿಜ್ಞಾನದಲ್ಲಿ ನೆನಪಿಡಿ: ದ್ರವ್ಯರಾಶಿ (Mass) ವಸ್ತುವಿನಲ್ಲಿರುವ ವಸ್ತುವಿನ ಪ್ರಮಾಣ, ಮತ್ತು ತೂಕ (Weight) ಅದರ ಮೇಲೆ ಕಾರ್ಯನಿರ್ವಹಿಸುವ ಗುರುತ್ವಾಕರ್ಷಣಾ ಬಲ: W = m * g.",
            "ta": "அறிவியலில் நினைவில் கொள்ளுங்கள்: நிறை (Mass) என்பது பொருளின் அளவு, எடை (Weight) என்பது அதன் மீது செயல்படும் ஈர்ப்பு விசை: W = m * g.",
            "te": "సైన్స్‌లో గుర్తుంచుకోండి: ద్రవ్యరాశి (Mass) అనేది పదార్థం యొక్క పరిమాణం, మరియు బరువు (Weight) అనేది దానిపై పనిచేసే గురుత్వాకర్షణ శక్తి: W = m * g.",
            "en": "In science, remember that mass is the amount of matter in an object, while weight is the gravitational force pulling on that mass: W = m * g.",
        }
        answer_text = science_answers.get(lang_prefix, science_answers["en"])
        captured_next_step = "How does your weight change if you go to the Moon where gravity is 1/6th of Earth?"

    else:
        defaults = {
            "hi": "मैंने आपका काम देखा है। आप आगे क्या हल करना चाहते हैं?",
            "kn": "ನಾನು ನಿಮ್ಮ ಬೋರ್ಡ್ ಪರಿಶೀಲಿಸಿದ್ದೇನೆ. ನೀವು ಮುಂದೆ ಏನನ್ನು ಕಲಿಯಲು ಬಯಸುತ್ತೀರಿ?",
            "ta": "உங்கள் பலகையை நான் மதிப்பாய்வு செய்துள்ளேன். அடுத்து நீங்கள் என்ன கற்க விரும்புகிறீர்கள்?",
            "te": "నేను మీ బోర్డును సమీక్షించాను. తర్వాత మీరు ఏమి నేర్చుకోవాలనుకుంటున్నారు?",
            "en": "I'm looking at your work on the whiteboard. What would you like to solve or explore next?",
        }
        answer_text = defaults.get(lang_prefix, defaults["en"])
        captured_next_step = "Click 'Check Work' to verify your step or 'Hint' for guidance!"

    if request.action == "check_work" and captured_verdict == "not_applicable":
        captured_verdict = "uncertain"

    return answer_text, captured_verdict, captured_steps, captured_next_step


# =====================================================================
# Main Multi-Tier Execution Entrypoint
# =====================================================================
async def execute_tutor_turn(request: TutorTurnRequest, record: SessionRecord) -> TutorTurnResponse:
    """
    Executes a tutor turn using the 3-Tier Resilient Cascade:
      Tier 1: Gemini Live WebSocket (gemini-3.8-live / gemini-2.0-flash-live-001)
      Tier 2: Multimodal generate_content (gemini-2.5-flash / gemini-2.0-flash)
      Tier 3: Emergency SymPy Local Socratic Rescue (Zero-crash 429 shield)
    """
    if not settings.is_gemini_configured:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not configured or set to 'replace_me' in backend/.env")

    from google.genai import types

    image_bytes = request.get_decoded_image_bytes()
    history_summary = record.get_history_summary()
    prompt_text = build_turn_prompt(request, history_summary)

    # Multimodal parts for Live
    turn_parts = []
    if image_bytes:
        turn_parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    turn_parts.append(types.Part.from_text(text=prompt_text))

    answer_text = ""
    captured_verdict: Optional[str] = None
    captured_steps: List[str] = []
    captured_next_step: Optional[str] = None
    is_fallback = False

    # -------------------------------------------------------------
    # Attempt Tier 1: Gemini Live WebSocket
    # -------------------------------------------------------------
    try:
        logger.info("Attempting Tier 1: Gemini Live WebSocket...")
        answer_text, captured_verdict, captured_steps, captured_next_step = await _execute_tier1_live(
            request, record, turn_parts
        )
    except Exception as t1_err:
        logger.warning(f"Tier 1 failed ({t1_err}). Escalating to Tier 2 (generate_content)...")

        # ---------------------------------------------------------
        # Attempt Tier 2: Multimodal generate_content
        # ---------------------------------------------------------
        try:
            answer_text, captured_verdict, captured_steps, captured_next_step = await _execute_tier2_generate_content(
                request, image_bytes, prompt_text
            )
        except Exception as t2_err:
            logger.warning(f"Tier 2 failed ({t2_err}). Escalating to Tier 3 (Emergency Rescue)...")

            # -----------------------------------------------------
            # Attempt Tier 3: Emergency Local Rescue
            # -----------------------------------------------------
            is_fallback = True
            answer_text, captured_verdict, captured_steps, captured_next_step = _execute_tier3_emergency_rescue(
                request, record
            )

    if not answer_text:
        if captured_verdict == "correct":
            answer_text = "Excellent work! Your step is mathematically correct."
        elif captured_verdict == "incorrect":
            answer_text = "I checked your step. There is an algebraic mistake in this step."
        else:
            answer_text = "I reviewed your work on the whiteboard. What would you like to explore next?"

    # Update session memory
    user_label = request.message if request.message else "[Shared Whiteboard]"
    record.append_turn("student", user_label)
    record.append_turn("tutor", answer_text)

    # Enforce Section 7D Verdict Rules
    verdict: VerdictType = "not_applicable"
    if captured_verdict in ("correct", "incorrect", "uncertain"):
        verdict = captured_verdict
    elif request.action == "check_work":
        eq_pair = extract_equations_from_message(request.message)
        if eq_pair:
            res = verify_equation_step(original_equation=eq_pair[0], current_step=eq_pair[1])
            verdict = res["status"]
            captured_steps.append(res["reason"])
            if res.get("expected_next_step"):
                captured_next_step = res["expected_next_step"]
        else:
            verdict = "uncertain"

    return TutorTurnResponse(
        session_id=request.session_id,
        answer=answer_text,
        language_code=request.language_code,
        verdict=verdict,
        transcript=request.message,
        steps=captured_steps,
        next_suggestion=captured_next_step or ("Ask for a hint or check your next step!" if request.action != "hint" else "Try applying this step on the board!"),
        fallback_mode=is_fallback
    )
