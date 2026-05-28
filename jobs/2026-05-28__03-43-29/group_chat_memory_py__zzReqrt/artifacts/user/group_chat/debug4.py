import inspect
from mem0 import MemoryClient

def main():
    print(inspect.signature(MemoryClient.add))

if __name__ == "__main__":
    main()