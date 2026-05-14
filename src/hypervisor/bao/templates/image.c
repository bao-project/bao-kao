{% if vm.image.expr %}
            .image = {{ vm.image.expr }},
{% else %}
            .image = {
{{ vm.image.struct_fields | render_fields("                ") }}
            },
{% endif %}