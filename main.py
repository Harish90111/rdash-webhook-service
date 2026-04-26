def main():
    print("Hello from rdash-webhook-service!")
    
    # Example: Process webhook data
    webhook_data = {
        "event": "test_event",
        "payload": {"message": "This is a dummy webhook"}
    }
    
    print(f"Processing webhook: {webhook_data}")
    print("Webhook processed successfully!")

if __name__ == "__main__":
    main()