import csv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

def plot_resources():
    times, cpu_usage, memory_usage, disk_usage = [], [], [], []

    # Read CSV file
    with open("resource_usage.csv", "r") as file:
        reader = csv.reader(file)
        next(reader)  # skip header
        for row in reader:
            times.append(row[0])
            cpu_usage.append(float(row[1]))
            memory_usage.append(float(row[2]))
            disk_usage.append(float(row[3]))

    # Convert time strings to datetime objects
    times = [datetime.strptime(t, "%H:%M:%S") for t in times]

    # Create figure
    plt.figure(figsize=(10, 6))

    # CPU usage
    plt.subplot(3, 1, 1)
    plt.plot(times, cpu_usage, label="CPU Usage (%)", color="r")
    plt.title("CPU Usage Over Time")
    plt.xlabel("Time")
    plt.ylabel("CPU (%)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # Memory usage
    plt.subplot(3, 1, 2)
    plt.plot(times, memory_usage, label="Memory Usage (%)", color="g")
    plt.title("Memory Usage Over Time")
    plt.xlabel("Time")
    plt.ylabel("Memory (%)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # Disk usage
    plt.subplot(3, 1, 3)
    plt.plot(times, disk_usage, label="Disk Usage (%)", color="b")
    plt.title("Disk Usage Over Time")
    plt.xlabel("Time")
    plt.ylabel("Disk (%)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout()

    # Save with timestamp so each run has unique file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"resource_usage_plot_{timestamp}.png"
    plt.savefig(filename)
    plt.close()

    print(f"✅ Plot saved as {filename}")

if __name__ == "__main__":
    plot_resources()
