from lambda_packer.exporters.oci import OCIExporter

def test_oci_exporter_default_tag():
    exporter = OCIExporter()
    tag = exporter.resolve_tag(name="my-lambda", arch="arm64")
    assert tag == "lambda-packer/my-lambda:arm64"

def test_oci_exporter_custom_tag():
    exporter = OCIExporter()
    tag = exporter.resolve_tag(
        name="my-lambda", 
        arch="amd64", 
        custom_tag="my-registry.com/{name}:v1-{arch}"
    )
    assert tag == "my-registry.com/my-lambda:v1-amd64"

def test_oci_exporter_args():
    exporter = OCIExporter()
    args = exporter.get_export_args(tags=["tag1"], push=True)
    assert args == {
        "output_type": "image",
        "tags": ["tag1"],
        "push": True
    }
