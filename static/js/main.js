// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {

    // =====================================================
    // СВОРАЧИВАНИЕ ПРИЁМОВ ПИЩИ
    // =====================================================

    // Обработка сворачивания - переключение иконки стрелки
    document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(function(header) {
        const targetId = header.getAttribute('data-bs-target');
        if (!targetId) return;

        const target = document.querySelector(targetId);
        if (!target) return;

        const mealKey = targetId.replace('#collapse-', '');
        const icon = document.getElementById('icon-' + mealKey);

        if (icon) {
            target.addEventListener('show.bs.collapse', function() {
                icon.classList.remove('bi-chevron-right');
                icon.classList.add('bi-chevron-down');
            });

            target.addEventListener('hide.bs.collapse', function() {
                icon.classList.remove('bi-chevron-down');
                icon.classList.add('bi-chevron-right');
            });
        }
    });

    // Предотвращаем сворачивание при клике на кнопки внутри заголовка
    document.querySelectorAll('.meal-card .card-header .btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });

    // =====================================================
    // ПОИСК ПРОДУКТОВ В МОДАЛЬНОМ ОКНЕ
    // =====================================================

    const productSearch = document.getElementById('productSearch');
    const productSelect = document.getElementById('productSelect');

    if (productSearch && productSelect) {
        productSearch.addEventListener('input', function() {
            const filter = this.value.toLowerCase();
            const options = productSelect.querySelectorAll('option');

            options.forEach(option => {
                const text = option.textContent.toLowerCase();
                option.style.display = text.includes(filter) ? '' : 'none';
            });
        });

        // Очистка поиска при открытии модального окна
        const addMealModal = document.getElementById('addMealModal');
        if (addMealModal) {
            addMealModal.addEventListener('show.bs.modal', function() {
                productSearch.value = '';
                const options = productSelect.querySelectorAll('option');
                options.forEach(option => {
                    option.style.display = '';
                });
            });
        }
    }

    // =====================================================
    // БЫСТРЫЕ КНОПКИ ВЕСА (50г, 100г, 150г, 200г)
    // =====================================================

    const weightBtns = document.querySelectorAll('.weight-btn');
    const weightInput = document.getElementById('weightInput');

    weightBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const weight = this.dataset.weight;
            if (weightInput) {
                weightInput.value = weight;
                weightInput.dispatchEvent(new Event('input'));

                // Подсветка активной кнопки
                weightBtns.forEach(b => b.classList.remove('active', 'btn-secondary'));
                weightBtns.forEach(b => b.classList.add('btn-outline-secondary'));
                this.classList.remove('btn-outline-secondary');
                this.classList.add('active', 'btn-secondary');
            }
        });
    });

    // Сброс подсветки при ручном вводе веса
    if (weightInput) {
        weightInput.addEventListener('input', function() {
            const value = this.value;
            weightBtns.forEach(btn => {
                if (btn.dataset.weight === value) {
                    btn.classList.remove('btn-outline-secondary');
                    btn.classList.add('active', 'btn-secondary');
                } else {
                    btn.classList.remove('active', 'btn-secondary');
                    btn.classList.add('btn-outline-secondary');
                }
            });
        });
    }

    // =====================================================
    // ПРЕДПРОСМОТР ПИЩЕВОЙ ЦЕННОСТИ
    // =====================================================

    function updateNutritionPreview() {
        const productSelect = document.getElementById('productSelect');
        const weightInput = document.getElementById('weightInput');

        if (!productSelect || !weightInput) return;

        const selectedOption = productSelect.options[productSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value) {
            // Сброс значений если продукт не выбран
            setPreviewValues(0, 0, 0, 0);
            return;
        }

        const weight = parseFloat(weightInput.value) || 0;
        const multiplier = weight / 100;

        const calories = parseFloat(selectedOption.dataset.calories) || 0;
        const protein = parseFloat(selectedOption.dataset.protein) || 0;
        const fat = parseFloat(selectedOption.dataset.fat) || 0;
        const carbs = parseFloat(selectedOption.dataset.carbs) || 0;

        setPreviewValues(
            Math.round(calories * multiplier),
            (protein * multiplier).toFixed(1),
            (fat * multiplier).toFixed(1),
            (carbs * multiplier).toFixed(1)
        );
    }

    function setPreviewValues(calories, protein, fat, carbs) {
        const previewCalories = document.getElementById('previewCalories');
        const previewProtein = document.getElementById('previewProtein');
        const previewFat = document.getElementById('previewFat');
        const previewCarbs = document.getElementById('previewCarbs');

        if (previewCalories) previewCalories.textContent = calories;
        if (previewProtein) previewProtein.textContent = protein;
        if (previewFat) previewFat.textContent = fat;
        if (previewCarbs) previewCarbs.textContent = carbs;
    }

    // Привязка событий для обновления предпросмотра
    if (productSelect) {
        productSelect.addEventListener('change', updateNutritionPreview);
    }

    if (weightInput) {
        weightInput.addEventListener('input', updateNutritionPreview);
    }

    // =====================================================
    // МОДАЛЬНОЕ ОКНО ДОБАВЛЕНИЯ ПРИЁМА ПИЩИ
    // =====================================================

    const addMealModal = document.getElementById('addMealModal');
    if (addMealModal) {
        addMealModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;

            // Установка типа приёма пищи из кнопки
            if (button) {
                const mealType = button.dataset.mealType;
                const modalMealType = document.getElementById('modalMealType');
                if (modalMealType && mealType) {
                    modalMealType.value = mealType;
                }
            }

            // Сброс формы
            const weightInput = document.getElementById('weightInput');
            if (weightInput) {
                weightInput.value = 100;
            }

            // Сброс кнопок веса
            document.querySelectorAll('.weight-btn').forEach(btn => {
                btn.classList.remove('active', 'btn-secondary');
                btn.classList.add('btn-outline-secondary');
                if (btn.dataset.weight === '100') {
                    btn.classList.remove('btn-outline-secondary');
                    btn.classList.add('active', 'btn-secondary');
                }
            });

            // Обновление предпросмотра
            setTimeout(updateNutritionPreview, 100);
        });

        // Сброс при закрытии модального окна
        addMealModal.addEventListener('hidden.bs.modal', function() {
            const productSearch = document.getElementById('productSearch');
            if (productSearch) {
                productSearch.value = '';
            }

            const productSelect = document.getElementById('productSelect');
            if (productSelect) {
                productSelect.selectedIndex = 0;
                const options = productSelect.querySelectorAll('option');
                options.forEach(option => {
                    option.style.display = '';
                });
            }

            setPreviewValues(0, 0, 0, 0);
        });
    }

    // Первоначальное обновление предпросмотра
    updateNutritionPreview();

    // =====================================================
    // ПОИСК НА СТРАНИЦЕ ПРОДУКТОВ
    // =====================================================

    const searchProductsInput = document.getElementById('searchProducts');
    const productsTable = document.getElementById('productsTable');

    if (searchProductsInput && productsTable) {
        searchProductsInput.addEventListener('input', function() {
            const filter = this.value.toLowerCase();
            const rows = productsTable.querySelectorAll('tbody tr');

            rows.forEach(row => {
                const name = row.cells[0].textContent.toLowerCase();
                row.style.display = name.includes(filter) ? '' : 'none';
            });
        });
    }

    // =====================================================
    // АВТОМАТИЧЕСКОЕ СКРЫТИЕ УВЕДОМЛЕНИЙ
    // =====================================================

    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            try {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                if (bsAlert) {
                    bsAlert.close();
                }
            } catch (e) {
                // Если Bootstrap Alert не доступен, скрываем вручную
                alert.style.transition = 'opacity 0.3s';
                alert.style.opacity = '0';
                setTimeout(() => {
                    alert.remove();
                }, 300);
            }
        }, 5000);
    });

    // =====================================================
    // ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ
    // =====================================================

    document.querySelectorAll('[data-confirm]').forEach(element => {
        element.addEventListener('click', function(e) {
            const message = this.dataset.confirm || 'Вы уверены?';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });

    // =====================================================
    // УТИЛИТЫ
    // =====================================================

    // Форматирование чисел
    window.formatNumber = function(num, decimals = 1) {
        return parseFloat(num).toFixed(decimals);
    };

    // API для поиска продуктов (асинхронный)
    window.searchProducts = async function(query) {
        try {
            const response = await fetch(`/api/search_products?q=${encodeURIComponent(query)}`);
            return await response.json();
        } catch (error) {
            console.error('Error searching products:', error);
            return [];
        }
    };

    // API для получения информации о продукте
    window.getProductNutrition = async function(productId, weight = 100) {
        try {
            const response = await fetch(`/api/product/${productId}?weight=${weight}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching product:', error);
            return null;
        }
    };

    // =====================================================
    // ДОБАВЛЕНИЕ ПРОДУКТА - ПЕРЕСЧЁТ НА 100Г
    // =====================================================

    const per100g = document.getElementById('per100g');
    const perCustom = document.getElementById('perCustom');
    const customServing = document.getElementById('customServing');
    const previewCard = document.getElementById('previewCard');

    const inputCalories = document.getElementById('inputCalories');
    const inputProtein = document.getElementById('inputProtein');
    const inputFat = document.getElementById('inputFat');
    const inputCarbs = document.getElementById('inputCarbs');

    const preview100Calories = document.getElementById('preview100Calories');
    const preview100Protein = document.getElementById('preview100Protein');
    const preview100Fat = document.getElementById('preview100Fat');
    const preview100Carbs = document.getElementById('preview100Carbs');

    function updateServingType() {
        if (!perCustom || !customServing || !previewCard) return;

        if (perCustom.checked) {
            customServing.disabled = false;
            customServing.focus();
            previewCard.style.display = 'block';
            updateProductPreview();
        } else {
            customServing.disabled = true;
            previewCard.style.display = 'none';
        }
    }

    function updateProductPreview() {
        if (!perCustom || !perCustom.checked) return;
        if (!customServing || !inputCalories) return;

        const serving = parseFloat(customServing.value) || 100;
        const multiplier = 100 / serving;

        const calories = parseFloat(inputCalories.value) || 0;
        const protein = parseFloat(inputProtein.value) || 0;
        const fat = parseFloat(inputFat.value) || 0;
        const carbs = parseFloat(inputCarbs.value) || 0;

        if (preview100Calories) preview100Calories.textContent = (calories * multiplier).toFixed(1);
        if (preview100Protein) preview100Protein.textContent = (protein * multiplier).toFixed(1);
        if (preview100Fat) preview100Fat.textContent = (fat * multiplier).toFixed(1);
        if (preview100Carbs) preview100Carbs.textContent = (carbs * multiplier).toFixed(1);
    }

    if (per100g) {
        per100g.addEventListener('change', updateServingType);
    }

    if (perCustom) {
        perCustom.addEventListener('change', updateServingType);
    }

    if (customServing) {
        customServing.addEventListener('input', updateProductPreview);
    }

    if (inputCalories) {
        inputCalories.addEventListener('input', updateProductPreview);
    }

    if (inputProtein) {
        inputProtein.addEventListener('input', updateProductPreview);
    }

    if (inputFat) {
        inputFat.addEventListener('input', updateProductPreview);
    }

    if (inputCarbs) {
        inputCarbs.addEventListener('input', updateProductPreview);
    }

    // =====================================================
    // КЛАВИАТУРНЫЕ СОКРАЩЕНИЯ
    // =====================================================

    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K - фокус на поиске
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('productSearch') ||
                               document.getElementById('searchProducts');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }

        // Escape - закрытие модальных окон
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal.show');
            openModals.forEach(modal => {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            });
        }
    });

    // =====================================================
    // ИНИЦИАЛИЗАЦИЯ TOOLTIPS (если используются)
    // =====================================================

    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined') {
        tooltipTriggerList.forEach(function(tooltipTriggerEl) {
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // =====================================================
    // CONSOLE LOG ДЛЯ ОТЛАДКИ
    // =====================================================

    console.log('🍎 Дневник питания загружен');
});