resource "null_resource" "example" {
  triggers = {
    value = "test-major-bump"
  }
}
