resource "null_resource" "infra" {
  triggers = {
    value = "test-pr-merge-release"
  }
}
