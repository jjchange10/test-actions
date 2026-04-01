resource "null_resource" "apps" {
  triggers = {
    value = "test-major-bump"
  }
}
