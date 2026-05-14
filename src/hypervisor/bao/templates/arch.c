{% if vm.platform.arch.gic_entries %}
                    .gic = {
{{ vm.platform.arch.gic_entries | render_fields("                        ") }}
                    }{% if vm.platform.arch.generic_entries %},{% endif %}
{% endif %}
{% if vm.platform.arch.generic_entries %}
{{ vm.platform.arch.generic_entries | render_fields("                    ") }}
{% endif %}
