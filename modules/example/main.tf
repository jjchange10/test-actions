resource "null_resource" "example" {
  triggers = {
    value = "test-skip-github-release"
  }
}
