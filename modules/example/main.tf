resource "null_resource" "example" {
  triggers = {
    value = "test-minor-bump"
  }
}
