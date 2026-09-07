import json, os, logging, asyncio
from openai import AsyncOpenAI
import openai
from prompt import SYSTEM_PROMPT
from validator import validate, ValidationError

log = logging.getLogger(__name__)

_client = None

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API"),
            base_url="https://api.deepseek.com",
        )
    return _client
class ParseFailed(Exception):
    """Model still failed after try about 1 or 2 times"""


async def parse_message(text: str) -> dict:
    return await _calling([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ])
    
    
async def answer_with_data(text:str, answer : dict, result) -> dict:
    return await _calling([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
        {"role": "assistant", "content": json.dumps(answer, default=str)},
        {"role": "user", "content":
            f"Hasil query dari database: {result}. "
            f"Jawab pertanyaan user memakai angka ini. Set query menjadi null."},
    ])


async def _calling(conversation, max_attempt=3) -> dict:
    for attempt in range(1,max_attempt + 1):
        #called the API
        try:
            response = await get_client().chat.completions.create(
                    model = "deepseek-v4-flash",
                    messages= conversation,
                    response_format = {"type" : "json_object"},
                    max_tokens = 1024,
                    temperature=0,
                )
            
        except(openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError):
            if attempt == max_attempt:
                raise
            await asyncio.sleep(2 ** attempt) 
            continue

        except(openai.AuthenticationError, openai.BadRequestError):
            raise

        content = response.choices[0].message.content or ""

        #Validation for the Model
        try:
            return validate(json.loads(content))
        except(json.JSONDecodeError, ValidationError) as e:
            log.warning("percobaan %d gagal: %s", attempt, e)
            if attempt == max_attempt:
                raise ParseFailed(str(e)) from e

            #give the feedback to the model
            conversation.append({"role" : "assistant", "content" : content})
            conversation.append({
                "role": "user",
                "content": f"Output json tadi salah: {e}. "
                f"Perbaiki, balas ulang hanya dengan json yang benar.",
            })
            
    
    raise ParseFailed("kehabisaan percobaan")
        
    
    
    
    
