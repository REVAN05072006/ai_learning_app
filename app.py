from flask import Flask, render_template, request, jsonify
import os
import json
import requests
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# GitHub AI configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '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')
MODEL_ENDPOINT = 'https://models.github.ai/inference'
MODEL_NAME = 'openai/gpt-4.1'

def generate_content(prompt, max_retries=3):
    headers = {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Content-Type': 'application/json'
    }

    data = {
        'messages': [
            {'role': 'system', 'content': 'You are an expert teacher who explains concepts clearly and engagingly. Provide detailed explanations with examples when teaching.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7,
        'top_p': 1.0,
        'model': MODEL_NAME
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                f'{MODEL_ENDPOINT}/chat/completions',
                headers=headers,
                json=data,
                timeout=20
            )
            
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = min((attempt + 1) * 5, 30)  # Exponential backoff up to 30 seconds
                    time.sleep(wait_time)
                    continue
                raise Exception("API rate limit exceeded. Please try again later.")
                
            if response.status_code == 401:
                raise Exception("Unauthorized - check your GitHub token permissions.")
                
            if response.status_code == 403:
                raise Exception("Forbidden - you may need to upgrade your access.")
                
            response.raise_for_status()
            
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not content:
                raise Exception("API returned empty content")
            return content
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                print(f"[API ERROR] {str(e)}")
                return None
            time.sleep(3)
            
    return None

def generate_lesson_content(topic):
    try:
        # Generate main lesson with more specific instructions
        lesson_prompt = (
            f"Create a comprehensive lesson about {topic} with these sections:\n"
            f"1. Introduction (overview and importance)\n"
            f"2. Key Concepts (detailed explanations with bullet points)\n"
            f"3. Examples (2-3 real-world applications with code snippets if applicable)\n"
            f"4. Summary (recap of main points)\n\n"
            f"Use Markdown formatting with ## for section headings, **bold** for key terms, "
            f"and ``` for code blocks. Keep paragraphs concise (2-3 sentences)."
        )
        
        lesson_content = generate_content(lesson_prompt)
        if not lesson_content:
            raise Exception("Failed to generate lesson content - API returned no data")

        # Generate quiz with strict JSON format instructions
        quiz_prompt = (
            f"Create a 5-question multiple choice quiz about {topic}.\n"
            f"Format as a JSON array where each question has:\n"
            f"- 'question' (string)\n"
            f"- 'options' (array of 4 strings)\n"
            f"- 'correct' (integer index of correct option)\n"
            f"- 'explanation' (string)\n\n"
            f"Questions should test understanding of key concepts from this lesson:\n"
            f"{lesson_content}\n\n"
            f"Return ONLY the JSON with no additional text or markdown."
        )
        
        quiz_content = generate_content(quiz_prompt)
        quiz_data = []
        
        if quiz_content:
            try:
                # Clean the response to extract pure JSON
                quiz_content = quiz_content.strip()
                if quiz_content.startswith('```json'):
                    quiz_content = quiz_content[7:-3].strip()
                elif quiz_content.startswith('```'):
                    quiz_content = quiz_content[3:-3].strip()
                
                quiz_data = json.loads(quiz_content)
                if not isinstance(quiz_data, list):
                    quiz_data = []
            except json.JSONDecodeError as e:
                print(f"[QUIZ PARSE ERROR] {str(e)}")
                quiz_data = []

        return {
            'success': True,
            'content': [{
                'title': f'Learning {topic}',
                'text': lesson_content,
                'example': ''
            }],
            'quiz': quiz_data
        }

    except Exception as e:
        print(f"[CONTENT ERROR] {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'content': [{
                'title': 'Error',
                'text': 'We encountered an issue generating the content. Please try again in a moment.',
                'example': ''
            }],
            'quiz': []
        }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_lesson', methods=['POST'])
def get_lesson():
    try:
        data = request.get_json()
        topic = data.get('topic', '').strip()
        if not topic:
            return jsonify({'success': False, 'error': 'Topic is required'}), 400

        lesson_data = generate_lesson_content(topic)
        return jsonify(lesson_data)

    except Exception as e:
        print(f"[SERVER ERROR] {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Server error occurred'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)