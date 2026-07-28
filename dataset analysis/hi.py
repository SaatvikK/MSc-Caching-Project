import pandas as pd

df = pd.read_csv('cache-u-00.tsv', sep='\t')

print("Unique hasedh path queries (request IDs):", df.hashed_path_query.nunique())

df.hashed_path_query = pd.factorize(df.hashed_path_query)[0]

print(df.hashed_path_query.nunique())

print("Remapped the request IDs")

print("Image types (items):", df.image_type.nunique())

df.image_type = pd.factorize(df.image_type)[0]

print("Remapped the items")

df = df.drop(columns="response_size")

print("Removed the response size column")

df.columns = ["time", "req", "item", "respTime"]

print("Renamed columns")

print("\n" + "=" * 60)
print("AUDIT OF CLEANED DATAFRAME")
print("=" * 60)

print("\nShape (rows, cols):", df.shape)
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Column names:", list(df.columns))

print("\nMemory usage:")
print(df.memory_usage(deep=True))
print("Total memory (MB):", df.memory_usage(deep=True).sum() / 1024**2)

print("\nDtypes:")
print(df.dtypes)

print("\nUnique values per column:")
print(df.nunique())

print("\nNulls per column:")
print(df.isna().sum())

print("\nDuplicate rows:", df.duplicated().sum())

print("\nDescribe (numeric):")
print(df.describe(include="all").transpose())

print("\nMin/max per column:")
for col in df.columns:
    print(f"  {col}: min={df[col].min()}, max={df[col].max()}")

print("\nitem value counts (remapped codes):")
print(df.item.value_counts())

print("\nreq frequency distribution (requests per unique req ID):")
print(df.req.value_counts().describe())

print("\nHead:")
print(df.head())

print("\nTail:")
print(df.tail())

print("=" * 60)

df.to_csv("cache-u-00-cleaned.csv", index=False)

print("Saved cleaned dataframe to cache-u-00-cleaned.csv")
