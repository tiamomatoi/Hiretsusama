# Use a Python version that supports Playwright
FROM ://microsoft.com

# Set the working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and its system dependencies
RUN playwright install --with-deps chromium

# Copy rest of code
COPY . .

# Start the bot
CMD ["python", "bot.py"]
