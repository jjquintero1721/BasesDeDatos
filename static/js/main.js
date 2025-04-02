// Funcionalidades JavaScript para la aplicación de Lavado de Vehículos

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips y popovers de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Función para obtener insumos al seleccionar un tipo de lavado
    const tipoLavadoSelect = document.getElementById('tipo_lavado');
    if (tipoLavadoSelect) {
        tipoLavadoSelect.addEventListener('change', function() {
            const tipoLavadoId = this.value;
            if (tipoLavadoId) {
                fetch(`/api/insumos-lavado/${tipoLavadoId}`)
                    .then(response => response.json())
                    .then(data => {
                        console.log('Insumos para este tipo de lavado:', data);
                        // Aquí se podrían mostrar los insumos asociados a este tipo de lavado
                    })
                    .catch(error => console.error('Error:', error));
            }
        });
    }

    // Función para cargar los insumos disponibles en el modal
    const usarInsumosModal = document.getElementById('usarInsumosModal');
    if (usarInsumosModal) {
        usarInsumosModal.addEventListener('show.bs.modal', function() {
            const insumoSelect = document.getElementById('insumo_id');
            
            // Limpiar opciones actuales
            while (insumoSelect.options.length > 1) {
                insumoSelect.remove(1);
            }
            
            // Cargar insumos disponibles
            fetch('/api/insumos-disponibles')
                .then(response => response.json())
                .then(data => {
                    data.forEach(insumo => {
                        const option = document.createElement('option');
                        option.value = insumo.ID;
                        option.textContent = `${insumo.nombre} (Stock: ${insumo.stock})`;
                        insumoSelect.appendChild(option);
                    });
                })
                .catch(error => console.error('Error:', error));
        });
    }

    // Función para validar formularios
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Actualizar automáticamente el precio según el tipo de vehículo y lavado
    const tipoVehiculoSelect = document.getElementById('tipo_vehiculo');
    if (tipoVehiculoSelect && tipoLavadoSelect) {
        const actualizarPrecio = function() {
            const tipoVehiculo = tipoVehiculoSelect.value;
            const tipoLavado = tipoLavadoSelect.value;
            
            if (tipoVehiculo && tipoLavado) {
                fetch(`/api/precio/${tipoVehiculo}/${tipoLavado}`)
                    .then(response => response.json())
                    .then(data => {
                        const precioElement = document.getElementById('precio');
                        if (precioElement) {
                            precioElement.value = data.precio;
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
        };
        
        tipoVehiculoSelect.addEventListener('change', actualizarPrecio);
        tipoLavadoSelect.addEventListener('change', actualizarPrecio);
    }

    // Filtrado dinámico de tabla
    const searchInput = document.getElementById('searchTable');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const searchText = this.value.toLowerCase();
            const tableRows = document.querySelectorAll('.data-table tbody tr');
            
            tableRows.forEach(row => {
                const shouldShow = Array.from(row.cells).some(cell => 
                    cell.textContent.toLowerCase().includes(searchText)
                );
                row.style.display = shouldShow ? '' : 'none';
            });
        });
    }
});