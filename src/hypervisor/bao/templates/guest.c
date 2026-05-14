        {
{% include "image.c" %}

            .entry = {{ vm.entry }},

            .platform = {
                .cpu_num = {{ vm.platform.cpu_num }},

                .region_num = {{ vm.platform.regions | length }},
                .regions = (struct vm_mem_region[]) {
{% for region in vm.platform.regions %}
{% include "mem_region.c" %}{{ "," if not loop.last else "" }}
{% endfor %}
                },

                .dev_num = {{ vm.platform.devs | length }},
                .devs = (struct vm_dev_region[]) {
{% for dev in vm.platform.devs %}
{% include "dev_region.c" %}{{ "," if not loop.last else "" }}
{% endfor %}
                }
{% if vm.platform.arch %},

                .arch = {
{% include "arch.c" %}
                }
{% endif %}
            },
        }
