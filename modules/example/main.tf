resource "null_resource" "example" {
  triggers = {
    value = "test-release-please"
  }
}
