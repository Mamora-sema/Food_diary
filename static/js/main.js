// static/js/main.js

// =====================================================
// ЛОКАЛЬНОЕ КЭШИРОВАНИЕ ДАННЫХ
// =====================================================

const AppCache = {
    CACHE_KEY: 'food_diary_cache',
    CACHE_VERSION: '1.0',

    // Получить данные из кэша
    get() {
        try {
            const cached = localStorage.getItem(this.CACHE_KEY);
            if (cached) {
                const data = JSON.parse(cached);
                if (data.version === this.CACHE_VERSION) {
                    return data;
                }
            }
        } catch (e) {
            console.error('Cache read error:', e);
        }
        return null;
    },

    // Сохранить данные в кэш
    set(data) {
        try {
            data.version = this.CACHE_VERSION;
            data.cachedAt = new Date().toISOString();
            localStorage.setItem(this.CACHE_KEY, JSON.stringify(data));
        } catch (e) {
            console.error('Cache write error:', e);
        }
    },

    // Очистить кэш
    clear() {
        localStorage.removeItem(this.CACHE_KEY);
    },

    // Проверить, актуален ли кэш (менее 5 минут)
    isValid() {
        const cached = this.get();
        if (!cached || !cached.cachedAt) return false;

        const cachedTime = new Date(cached.cachedAt).getTime();
        const now = new Date().getTime();
        const fiveMinutes = 5 * 60 * 1000;

        return (now - cachedTime) < fiveMinutes;
    }
};

// =====================================================
// ОЧЕРЕДЬ ИЗМЕНЕНИЙ ДЛЯ ОФФЛАЙН РЕЖИМА
// =====================================================

const OfflineQueue = {
    QUEUE_KEY: 'food_diary_queue',

    get() {
        try {
            const queue = localStorage.getItem(this.QUEUE_KEY);
            return queue ? JSON.parse(queue) : { new_entries: [], deleted_entries: [], new_products: [], deleted_products: [] };
        } catch (e) {
            return { new_entries: [], deleted_entries: [], new_products: [], deleted_products: [] };
        }
    },

    set(queue) {
        localStorage.setItem(this.QUEUE_KEY, JSON.stringify(queue));
    },

    addEntry(entry) {
        const queue = this.get();
        entry._tempId = 'temp_' + Date.now();
        queue.new_entries.push(entry);
        this.set(queue);
        return entry._tempId;
    },

    deleteEntry(entryId) {
        const queue = this.get();
        // Если это временная запись - просто удаляем из очереди
        if (String(entryId).startsWith('temp_')) {
            queue.new_entries = queue.new_entries.filter(e => e._tempId !== entryId);
        } else {
            queue.deleted_entries.push(entryId);
        }
        this.set(queue);
    },

    addProduct(product) {
        const queue = this.get();
        product._tempId = 'temp_' + Date.now();
        queue.new_products.push(product);
        this.set(queue);
        return product._tempId;
    },

    clear() {
        localStorage.removeItem(this.QUEUE_KEY);
    },

    hasChanges() {
        const queue = this.get();
        return queue.new_entries.length > 0 ||
               queue.deleted_entries.length > 0 ||
               queue.new_products.length > 0 ||
               queue.deleted_products.length > 0;
    }
};

// =====================================================
// API ФУНКЦИИ
// =====================================================

const API = {
    // Синхронизация всех данных
    async syncAll() {
        try {
            const response = await fetch('/api/sync');
            if (!response.ok) throw new Error('Sync failed');

            const result = await response.json();
            if (result.success) {
                AppCache.set(result);
                return result.data;
            }
            throw new Error(result.error || 'Sync failed');
        } catch (e) {
            console.error('Sync error:', e);
            // Возвращаем кэшированные данные при ошибке
            const cached = AppCache.get();
            return cached ? cached.data : null;
        }
    },

    // Отправка изменений
    async pushChanges() {
        if (!OfflineQueue.hasChanges()) return true;

        try {
            const queue = OfflineQueue.get();
            const response = await fetch('/api/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(queue)
            });

            if (response.ok) {
                OfflineQueue.clear();
                return true;
            }
            return false;
        } catch (e) {
            console.error('Push error:', e);
            return false;
        }
    },

    // Добавить запись приёма пищи
    async addEntry(entry) {
        try {
            const response = await fetch('/api/add_entry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(entry)
            });

            if (response.ok) {
                const result = await response.json();
                return result.entry;
            }
            throw new Error('Add entry failed');
        } catch (e) {
            // Добавляем в оффлайн очередь
            console.warn('Adding to offline queue:', e);
            const tempId = OfflineQueue.addEntry(entry);
            return { ...entry, id: tempId, _offline: true };
        }
    },

    // Удалить запись
    async deleteEntry(entryId) {
        try {
            const response = await fetch(`/api/delete_entry/${entryId}`, {
                method: 'DELETE'
            });
            return response.ok;
        } catch (e) {
            OfflineQueue.deleteEntry(entryId);
            return true;
        }
    },

    // Добавить продукт
    async addProduct(product) {
        try {
            const response = await fetch('/api/add_product', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(product)
            });

            if (response.ok) {
                const result = await response.json();
                return result.product;
            }
            throw new Error('Add product failed');
        } catch (e) {
            const tempId = OfflineQueue.addProduct(product);
            return { ...product, id: tempId, _offline: true };
        }
    }
};

// =====================================================
// КАЛЬКУЛЯТОР КБЖУ
// =====================================================

const NutritionCalc = {
    // Расчёт калорий из БЖУ
    calculateCalories(protein, fat, carbs) {
        return Math.round((protein * 4) + (fat * 9) + (carbs * 4));
    },

    // Расчёт питательности для веса
    forWeight(product, weight) {
        const multiplier = weight / 100;
        return {
            calories: Math.round(product.calories * multiplier * 10) / 10,
            protein: Math.round(product.protein * multiplier * 10) / 10,
            fat: Math.round(product.fat * multiplier * 10) / 10,
            carbs: Math.round(product.carbs * multiplier * 10) / 10
        };
    },

    // Суммирование записей
    sumEntries(entries) {
        return entries.reduce((sum, entry) => {
            const nutrition = entry.nutrition || this.forWeight(entry.product || entry, entry.weight);
            return {
                calories: sum.calories + nutrition.calories,
                protein: sum.protein + nutrition.protein,
                fat: sum.fat + nutrition.fat,
                carbs: sum.carbs + nutrition.carbs
            };
        }, { calories: 0, protein: 0, fat: 0, carbs: 0 });
    }
};

// =====================================================
// ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ
// =====================================================

document.addEventListener('DOMContentLoaded', function() {

    // Синхронизация при загрузке страницы
    if (!AppCache.isValid()) {
        API.syncAll().then(data => {
            if (data) {
                console.log('Data synced:', data);
                // Здесь можно обновить UI если нужно
            }
        });
    }

    // Попытка отправить оффлайн изменения
    if (OfflineQueue.hasChanges() && navigator.onLine) {
        API.pushChanges().then(success => {
            if (success) {
                console.log('Offline changes pushed');
                showToast('Данные синхронизированы', 'success');
            }
        });
    }

    // =====================================================
    // СВОРАЧИВАНИЕ ПРИЁМОВ ПИЩИ
    // =====================================================

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

    // =====================================================
    // ПОИСК ПРОДУКТОВ
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
    }

    // =====================================================
    // КНОПКИ ВЕСА
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

                weightBtns.forEach(b => b.classList.remove('active', 'btn-success'));
                this.classList.add('active', 'btn-success');
            }
        });
    });

    // =====================================================
    // ПРЕДПРОСМОТР ПИТАТЕЛЬНОСТИ
    // =====================================================

    function updateNutritionPreview() {
        const productSelect = document.getElementById('productSelect');
        const weightInput = document.getElementById('weightInput');

        if (!productSelect || !weightInput) return;

        const selectedOption = productSelect.options[productSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value) {
            setPreviewValues(0, 0, 0, 0);
            return;
        }

        const weight = parseFloat(weightInput.value) || 0;
        const product = {
            calories: parseFloat(selectedOption.dataset.calories) || 0,
            protein: parseFloat(selectedOption.dataset.protein) || 0,
            fat: parseFloat(selectedOption.dataset.fat) || 0,
            carbs: parseFloat(selectedOption.dataset.carbs) || 0
        };

        const nutrition = NutritionCalc.forWeight(product, weight);
        setPreviewValues(
            Math.round(nutrition.calories),
            nutrition.protein.toFixed(1),
            nutrition.fat.toFixed(1),
            nutrition.carbs.toFixed(1)
        );
    }

    function setPreviewValues(calories, protein, fat, carbs) {
        const els = {
            calories: document.getElementById('previewCalories'),
            protein: document.getElementById('previewProtein'),
            fat: document.getElementById('previewFat'),
            carbs: document.getElementById('previewCarbs')
        };

        if (els.calories) els.calories.textContent = calories;
        if (els.protein) els.protein.textContent = protein;
        if (els.fat) els.fat.textContent = fat;
        if (els.carbs) els.carbs.textContent = carbs;
    }

    if (productSelect) {
        productSelect.addEventListener('change', updateNutritionPreview);
    }

    if (weightInput) {
        weightInput.addEventListener('input', updateNutritionPreview);
    }

    // =====================================================
    // МОДАЛЬНОЕ ОКНО
    // =====================================================

    const addMealModal = document.getElementById('addMealModal');
    if (addMealModal) {
        addMealModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;

            if (button) {
                const mealType = button.dataset.mealType;
                const modalMealType = document.getElementById('modalMealType');
                if (modalMealType && mealType) {
                    modalMealType.value = mealType;
                }
            }

            // Reset
            if (weightInput) weightInput.value = 100;
            if (productSearch) productSearch.value = '';

            weightBtns.forEach(btn => {
                btn.classList.remove('active', 'btn-success');
                if (btn.dataset.weight === '100') {
                    btn.classList.add('active', 'btn-success');
                }
            });

            setTimeout(updateNutritionPreview, 100);
        });