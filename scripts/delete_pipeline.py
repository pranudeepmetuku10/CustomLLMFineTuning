from google.cloud import aiplatform


def cancel_training_pipeline_sample(
    project: str,
    training_pipeline_id: str,
    location: str = "us-central1",
    api_endpoint: str = "us-central1-aiplatform.googleapis.com",
):
    # The AI Platform services require regional API endpoints.
    client_options = {"api_endpoint": api_endpoint}
    # Initialize client that will be used to create and send requests.
    # This client only needs to be created once, and can be reused for multiple requests.
    client = aiplatform.gapic.PipelineServiceClient(client_options=client_options)
    name = client.training_pipeline_path(
        project=project, location=location, training_pipeline=training_pipeline_id
    )
    response = client.cancel_training_pipeline(name=name)
    print("response:", response)

cancel_training_pipeline_sample(project="llm-finetuning-480620", training_pipeline_id="4437884342819094528")