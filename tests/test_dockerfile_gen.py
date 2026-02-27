from lambda_packer.builders.dockerfile_gen import DockerfileGenerator

def test_dockerfile_gen_zip_no_layers():
    generator = DockerfileGenerator()
    df = generator.generate(
        runtime="python3.12",
        requirements=True,
        is_image=False
    )
    
    assert "FROM python:3.12-slim AS builder" in df
    assert "COPY requirements.txt" in df
    assert "FROM scratch" in df
    assert "COPY --from=builder /asset /" in df
    assert "layer-" not in df

def test_dockerfile_gen_image_with_layers():
    generator = DockerfileGenerator()
    df = generator.generate(
        runtime="python3.12",
        requirements=False,
        layers=["common"],
        layer_requirements={"common": True},
        is_image=True,
        handler="app.handler"
    )
    
    assert "FROM python:3.12-slim AS layer-common" in df
    assert "COPY layer_common_requirements.txt" in df
    assert "FROM public.ecr.aws/lambda/python:3.12" in df
    assert 'CMD [ "app.handler" ]' in df
    assert "COPY --from=layer-common /asset/python/ ." in df
