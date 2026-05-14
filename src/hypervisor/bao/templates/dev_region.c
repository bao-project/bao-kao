                    {
{% if dev.comment %}
                        /* {{ dev.comment }} */
{% endif %}
{{ dev.fields | render_fields("                        ") }}
                    }
