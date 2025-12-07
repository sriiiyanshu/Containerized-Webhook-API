#!/bin/bash

# Function to send a webhook message
send_webhook() {
    local body="$1"
    local sig=$(echo -n "$body" | openssl dgst -sha256 -hmac "testsecret" | awk '{print $2}')
    local status=$(curl -s -w "%{http_code}" -o /dev/null \
        -H "Content-Type: application/json" \
        -H "X-Signature: $sig" \
        -d "$body" \
        http://localhost:8000/webhook)
    echo "$status"
}

# Send messages
echo "Sending m2..."
send_webhook '{"message_id":"m2","from":"+919876543210","to":"+14155550101","ts":"2025-01-15T10:05:00Z","text":"Second message"}'

echo "Sending m3..."
send_webhook '{"message_id":"m3","from":"+14155550200","to":"+14155550100","ts":"2025-01-15T10:10:00Z","text":"Third message"}'

echo "Sending m4..."
send_webhook '{"message_id":"m4","from":"+919876543210","to":"+14155550102","ts":"2025-01-15T10:15:00Z","text":"Fourth message"}'

echo "Sending m5..."
send_webhook '{"message_id":"m5","from":"+14155550300","to":"+14155550100","ts":"2025-01-15T10:20:00Z","text":"Testing search Hello"}'

echo "Sending m6..."
send_webhook '{"message_id":"m6","from":"+14155550200","to":"+14155550101","ts":"2025-01-15T10:25:00Z","text":"Another one"}'

echo "✅ All messages sent!"
