resource "null_resource" "example" {
  triggers = {
    value = "test-auto-tag-v2"
  }
}
