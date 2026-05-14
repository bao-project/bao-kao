#include <config.h>

{% for img in declared_images %}
VM_IMAGE({{ img.symbol }}, XSTR(BAO_WRKDIR_IMGS/{{ img.bin_name }}.bin))
{% endfor %}

struct config config = {

    CONFIG_HEADER

    .vmlist_size = {{ num_vms }},
    .vmlist = (struct vm_config[]) {
{% for vm in vms %}
{% include "guest.c" %}{{ "," if not loop.last else "" }}
{% endfor %}
    },
};