(function() {
    $(document).ready(function() {
        // Global settings
        let distanceUnit = localStorage.getItem('distanceUnit') || 'miles';
        let currentSort = {
            column: 'date',
            direction: 'desc'
        };

        // Load initial data
        loadRoutes();
        updateMap();
        updateStatistics();

        // Handle form submission
        $('#routeForm').submit(function(e) {
            e.preventDefault();
            
            const startAddress = $('#startAddress').val();
            const endAddress = $('#endAddress').val();
            const notes = $('#notes').val();
            
            $.ajax({
                url: '/add_route',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    start_address: startAddress,
                    end_address: endAddress,
                    notes: notes
                }),
                success: function(response) {
                    if (response.success) {
                        $('#startAddress').val('');
                        $('#endAddress').val('');
                        $('#notes').val('');
                        loadRoutes();
                        updateMap();
                        updateStatistics();
                    } else {
                        alert('Error: Could not calculate route');
                    }
                },
                error: function() {
                    alert('Error: Could not add route');
                }
            });
        });

        // Handle restore form submission
        $('#restoreForm').submit(function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            formData.append('backup_file', $('#backupFile')[0].files[0]);
            
            $.ajax({
                url: '/restore_database',
                method: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                success: function(response) {
                    if (response.success) {
                        $('#restoreModal').modal('hide');
                        loadRoutes();
                        updateMap();
                        updateStatistics();
                    } else {
                        alert('Error: ' + response.error);
                    }
                },
                error: function() {
                    alert('Error: Could not restore database');
                }
            });
        });

        // Handle edit route form submission
        $('#editRouteForm').submit(function(e) {
            e.preventDefault();
            
            const routeId = $('#editRouteId').val();
            const startAddress = $('#editStartAddress').val();
            const endAddress = $('#editEndAddress').val();
            const notes = $('#editNotes').val();
            
            $.ajax({
                url: '/update_route/' + routeId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify({ 
                    start_address: startAddress,
                    end_address: endAddress,
                    notes: notes 
                }),
                success: function(response) {
                    if (response.success) {
                        $('#editRouteModal').modal('hide');
                        loadRoutes();
                        updateMap();
                        updateStatistics();
                    } else {
                        alert('Error: ' + (response.error || 'Could not update route'));
                    }
                },
                error: function() {
                    alert('Error: Could not update route');
                }
            });
        });

        // Handle address file upload form submission
        $('#uploadAddressesForm').on('submit', function(e) {
            e.preventDefault();
            console.log('Form submission started');
            
            const fileInput = $('#addressFile')[0];
            const startAddress = $('#uploadStartAddress').val().trim();
            
            console.log('File input:', fileInput.files[0]?.name || 'No file');
            console.log('Start address:', startAddress);
            
            if (!fileInput.files.length || !startAddress) {
                console.log('Validation failed - missing file or start address');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('startAddress', startAddress);
            
            console.log('FormData created with file and start address');
            
            // Show progress elements
            $('#uploadProgress').removeClass('d-none');
            const progressBar = $('#uploadProgress .progress-bar');
            const processingLog = $('#processingLog');
            progressBar.css('width', '0%');
            processingLog.empty();
            
            console.log('Progress UI elements initialized');
            
            // Clear previous status
            $('#uploadStatus').empty();
            
            // Disable the submit button
            const submitButton = $(this).find('button[type="submit"]');
            submitButton.prop('disabled', true);
            submitButton.html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...');
            
            console.log('Starting fetch request to /upload_addresses');
            
            // Create fetch request with streaming response
            fetch('/upload_addresses', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('Received initial response:', response.status, response.statusText);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                function processStream({ done, value }) {
                    if (done) {
                        console.log('Stream processing complete');
                        submitButton.prop('disabled', false);
                        submitButton.html('Upload and Process');
                        return;
                    }
                    
                    // Process chunks of data
                    const chunk = decoder.decode(value);
                    console.log('Received chunk:', chunk);
                    
                    const lines = chunk.split('\n');
                    
                    lines.forEach(line => {
                        if (!line) return;
                        
                        try {
                            console.log('Processing line:', line);
                            const data = JSON.parse(line);
                            console.log('Parsed data:', data);
                            
                            if (data.type === 'progress') {
                                console.log('Progress update:', data.progress + '%', data.current + '/' + data.total);
                                // Update progress bar and counts
                                progressBar.css('width', data.progress + '%');
                                $('#processCount').text(`${data.current}/${data.total}`);
                                $('#currentAddress').text(`Processing: ${data.address}`);
                                
                                // Add to processing log
                                const logEntry = $('<div>').addClass('mb-1');
                                if (data.success) {
                                    logEntry.addClass('text-success')
                                           .html(`✓ ${data.address}`);
                                } else {
                                    logEntry.addClass('text-danger')
                                           .html(`✗ ${data.address} - ${data.error}`);
                                }
                                processingLog.prepend(logEntry);
                                processingLog.scrollTop(0);
                            }
                            else if (data.type === 'complete') {
                                console.log('Processing complete:', data);
                                const successful = data.successful;
                                const total = data.total;
                                
                                $('#uploadStatus').html(`
                                    <div class="alert alert-success">
                                        Successfully processed ${successful} out of ${total} destinations.
                                        ${successful < total ? `<br>Some destinations failed - see log above for details.` : ''}
                                    </div>
                                `);
                                
                                $('#currentAddress').text('Processing complete');
                                $('#processCount').text(`${successful}/${total} successful`);
                                
                                loadRoutes();
                                updateMap();
                                updateStatistics();
                                
                                setTimeout(() => {
                                    fileInput.value = '';
                                    $('#uploadStartAddress').val('');
                                    $('#uploadProgress').addClass('d-none');
                                    progressBar.css('width', '0%');
                                    submitButton.prop('disabled', false);
                                    submitButton.html('Upload and Process');
                                }, 5000);
                            }
                            else if (data.type === 'error') {
                                console.error('Server reported error:', data.error);
                                $('#uploadStatus').html(`
                                    <div class="alert alert-danger">
                                        Error: ${data.error}
                                    </div>
                                `);
                                $('#uploadProgress').addClass('d-none');
                                submitButton.prop('disabled', false);
                                submitButton.html('Upload and Process');
                            }
                        } catch (e) {
                            console.error('Error parsing response line:', e, line);
                        }
                    });
                    
                    return reader.read().then(processStream);
                }
                
                return reader.read().then(processStream);
            })
            .catch(error => {
                console.error('Fetch error:', error);
                $('#uploadStatus').html(`
                    <div class="alert alert-danger">
                        Error uploading file. Please try again.
                    </div>
                `);
                $('#uploadProgress').addClass('d-none');
                submitButton.prop('disabled', false);
                submitButton.html('Upload and Process');
            });
        });

        // ... rest of the code remains the same ...

        function kmToMiles(km) {
            return km * 0.621371;
        }

        function formatDistance(km) {
            const distanceUnit = localStorage.getItem('distanceUnit') || 'miles';
            const distance = distanceUnit === 'miles' ? kmToMiles(km) : km;
            return distance.toFixed(2);
        }

        function getUnitSuffix() {
            const distanceUnit = localStorage.getItem('distanceUnit') || 'miles';
            return distanceUnit === 'miles' ? 'mi' : 'km';
        }

        function loadRoutes() {
            $.get('/get_routes', function(routes) {
                const tbody = $('#routesList');
                tbody.empty();
                
                // Sort routes based on current sort settings
                routes.sort((a, b) => {
                    let aVal = a[currentSort.column];
                    let bVal = b[currentSort.column];
                    
                    // Handle numeric values
                    if (currentSort.column === 'distance') {
                        aVal = parseFloat(aVal);
                        bVal = parseFloat(bVal);
                    }
                    
                    // Handle date values
                    if (currentSort.column === 'date') {
                        aVal = new Date(aVal);
                        bVal = new Date(bVal);
                    }
                    
                    if (aVal < bVal) return currentSort.direction === 'asc' ? -1 : 1;
                    if (aVal > bVal) return currentSort.direction === 'asc' ? 1 : -1;
                    return 0;
                });

                routes.forEach(function(route) {
                    const row = $('<tr>');
                    row.append($('<td>').text(route.start));
                    row.append($('<td>').text(route.end));
                    row.append($('<td>').text(formatDistance(route.distance)));
                    row.append($('<td>').text(new Date(route.date).toLocaleDateString()));
                    
                    const actionsCell = $('<td>');
                    const editBtn = $('<button>')
                        .addClass('btn btn-sm btn-primary me-2')
                        .html('<i class="bi bi-pencil"></i>')
                        .click(() => editRoute(route.id, route.start, route.end, route.notes));
                    
                    const deleteBtn = $('<button>')
                        .addClass('btn btn-sm btn-danger')
                        .html('<i class="bi bi-trash"></i>')
                        .click(() => deleteRoute(route.id));
                    
                    actionsCell.append(editBtn, deleteBtn);
                    row.append(actionsCell);
                    
                    tbody.append(row);
                });
            });
        }

        function updateMap() {
            console.log("Updating map...");
            fetch('/get_map')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error("Error loading map:", data.error);
                        return;
                    }
                    const mapContainer = document.getElementById('map');
                    mapContainer.innerHTML = data.html;
                    
                    // Log if map was regenerated
                    if (data.regenerated) {
                        console.log("Map was regenerated due to data changes");
                    } else {
                        console.log("Map loaded from cache");
                    }
                })
                .catch(error => {
                    console.error("Error fetching map:", error);
                });
        }

        function updateStatistics() {
            $.get('/get_statistics', function(stats) {
                $('#totalRoutes').text(stats.total_routes);
                $('#totalDistance').text(`${formatDistance(stats.total_distance)} ${getUnitSuffix()}`);
                $('#avgDistance').text(`${formatDistance(stats.average_distance)} ${getUnitSuffix()}`);
            });
        }

        function updateDistanceHeader() {
            const unit = localStorage.getItem('distanceUnit') || 'miles';
            const unitText = unit === 'miles' ? 'mi' : 'km';
            $('.sortable[data-sort="distance"]').html(`Distance (${unitText}) <i class="bi bi-arrow-down-up"></i>`);
        }

        function deleteRoute(routeId) {
            console.log('Attempting to delete route:', routeId);  
            if (confirm('Are you sure you want to delete this route?')) {
                $.ajax({
                    url: '/delete_route/' + routeId,
                    method: 'DELETE',
                    success: function(response) {
                        console.log('Delete route response:', response);  
                        if (response.success) {
                            // Reload the page to trigger map regeneration
                            location.reload();
                        } else {
                            console.error('Delete route failed:', response);  
                            alert('Error: Could not delete route');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Delete route AJAX error:', status, error);  
                        alert('Error: Could not delete route');
                    }
                });
            }
        }

        function editRoute(routeId, startAddr, endAddr, notes) {
            $('#editRouteId').val(routeId);
            $('#editStartAddress').val(startAddr);
            $('#editEndAddress').val(endAddr);
            $('#editNotes').val(notes);
            $('#editRouteModal').modal('show');
        }

        function exportCSV() {
            console.log('Attempting to export CSV');
            window.location.href = '/export_csv';
        }

        function backupDatabase() {
            $.post('/backup_database', function(response) {
                if (response.success) {
                    alert('Database backed up successfully');
                } else {
                    alert('Error: Could not backup database');
                }
            });
        }

        function clearDatabase() {
            console.log('Attempting to clear database');  // Add logging
            if (confirm('Are you sure you want to clear all routes? This cannot be undone!')) {
                $.ajax({
                    url: '/clear_database',
                    method: 'POST',
                    success: function(response) {
                        console.log('Clear database response:', response);  // Add logging
                        if (response.success) {
                            // Reload the page to trigger map regeneration
                            location.reload();
                        } else {
                            console.error('Clear database failed:', response);  
                            alert('Error: Could not clear database');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Clear database AJAX error:', status, error);  
                        alert('Error: Could not clear database');
                    }
                });
            }
        }

        function setTheme(theme) {
            const body = $('body');
            const buttons = $('.btn-outline-light');
            
            if (theme === 'light') {
                body.removeClass('bg-dark text-light').addClass('bg-light text-dark');
                $('.card').removeClass('bg-secondary').addClass('bg-white');
                $('.table').removeClass('table-dark');
                $('.modal-content').removeClass('bg-dark').addClass('bg-light');
                buttons.removeClass('active');
                buttons.first().addClass('active');
            } else {
                body.removeClass('bg-light text-dark').addClass('bg-dark text-light');
                $('.card').removeClass('bg-white').addClass('bg-secondary');
                $('.table').addClass('table-dark');
                $('.modal-content').removeClass('bg-light').addClass('bg-dark');
                buttons.removeClass('active');
                buttons.last().addClass('active');
            }
        }

        function setUnit(unit) {
            localStorage.setItem('distanceUnit', unit);
            updateDistanceHeader();
            loadRoutes();
        }

        // On page load, check for map updates
        document.addEventListener('DOMContentLoaded', function() {
            console.log("Checking for map updates...");
            updateMap();
            loadRoutes();
            updateStatistics();
        });

        // Add click handlers for sortable columns
        $(document).ready(function() {
            updateDistanceHeader();
            $('.sortable').click(function() {
                const column = $(this).data('sort');
                
                // Update sort direction
                if (currentSort.column === column) {
                    currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    currentSort.column = column;
                    currentSort.direction = 'asc';
                }
                
                // Update sort indicators
                $('.sortable').removeClass('asc desc');
                $(this).addClass(currentSort.direction);
                
                // Reload routes with new sort
                loadRoutes();
            });
        });

        // Expose functions globally
        window.deleteRoute = function(routeId) {
            console.log('Attempting to delete route:', routeId);  
            if (confirm('Are you sure you want to delete this route?')) {
                $.ajax({
                    url: '/delete_route/' + routeId,
                    method: 'DELETE',
                    success: function(response) {
                        console.log('Delete route response:', response);  
                        if (response.success) {
                            // Reload the page to trigger map regeneration
                            location.reload();
                        } else {
                            console.error('Delete route failed:', response);  
                            alert('Error: Could not delete route');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Delete route AJAX error:', status, error);  
                        alert('Error: Could not delete route');
                    }
                });
            }
        };

        // Expose clearDatabase globally with the same implementation as inside the IIFE
        window.clearDatabase = function() {
            console.log('Attempting to clear database');  
            if (confirm('Are you sure you want to clear all routes? This cannot be undone!')) {
                $.ajax({
                    url: '/clear_database',
                    method: 'POST',
                    success: function(response) {
                        console.log('Clear database response:', response);  
                        if (response.success) {
                            // Reload the page to trigger map regeneration
                            location.reload();
                        } else {
                            console.error('Clear database failed:', response);  
                            alert('Error: Could not clear database');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Clear database AJAX error:', status, error);  
                        alert('Error: Could not clear database');
                    }
                });
            }
        };

        // Expose exportCSV globally
        window.exportCSV = function() {
            console.log('Attempting to export CSV');
            window.location.href = '/export_csv';
        };

        // Expose other functions globally
        window.editRoute = editRoute;
        window.backupDatabase = backupDatabase;
        window.setTheme = setTheme;
        window.setUnit = setUnit;
    });

})();
