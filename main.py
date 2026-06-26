from langchain.agents import create_agent
from dotenv import load_dotenv
load_dotenv()


SYSTEM_PROMPT= '''
    You are a Customer Support Email Classifier. Your sole purpose is to classify the emails into their respective categories.
    
    Category: billing, technical, account, general
    output:
    1. After reviewing the email, classify the category from the above category list and summarize the email in 2-3 lines.  
    2. Return in a JSON format as shown below 
            {
                category: {category},
                summary: {email summary}
            }
    3. If unable to classify return as "Unable to answer due to missing context".
'''


dummy_mails = [
    '''Dear Aandy,

Thank you for contacting us. We sincerely apologize for the delay in delivering your order.

We have checked your order status, and it is currently in transit. The estimated delivery date is [Date]. We understand the inconvenience this may have caused and appreciate your patience.

If you have any further questions or need additional assistance, please feel free to reply to this email.

Thank you for choosing us.

Best regards,

Customer Support Team'''
]


agent = create_agent(
    model="google_genai:gemini-2.5-flash-lite",
    system_prompt=SYSTEM_PROMPT
)

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": dummy_mails[0]
                
            }
        ]
    }
)

print(result)